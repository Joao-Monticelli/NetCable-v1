"""Manual checks, ping and network discovery."""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
import time
from pydantic import BaseModel
from typing import Optional
from ..snmp_service import discover_neighbors, SNMPUnavailableError
from .. import models, crud
from .. import regras_alerta, descoberta, cabos_lldp, snmp_service
from ..nucleo import abrir_config, get_db, logger, requer_editor
from ..snmp_service import SNMPUnavailableError as _SemSnmp
from ..monitoramento import checar_equipamento, enviar_alertas, ping_equipamento, registrar_monitoramento
from fastapi import APIRouter

router = APIRouter()


# --- MONITORAMENTO E DESCOBERTA ---
class MonitorRequest(BaseModel):
    equipmentId: Optional[str] = None
    ip: str
    mode: str = "ip"
    config: Optional[dict] = None


@router.post("/api/monitor")
def monitor_equipamento(request: MonitorRequest, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    equipment = None
    if request.equipmentId:
        equipment = crud.get_equipamento(db, request.equipmentId)
        if not equipment:
            raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    config = request.config or {}
    if request.mode == "snmpv3" and equipment and not config.get("authPassword"):
        config = abrir_config(equipment.monitor_config)
    try:
        result = checar_equipamento(request.ip, request.mode, config)
    except SNMPUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    evento = registrar_monitoramento(db, equipment, result)
    enviar_alertas(db, regras_alerta.aplicar(db, [evento] if evento else []))
    return result


class DiscoveryRequest(BaseModel):
    ip: str
    config: dict


@router.post("/api/discovery/neighbors")
def descobrir_vizinhos(request: DiscoveryRequest, user: models.Usuario = Depends(requer_editor)):
    config = {**request.config, "host": request.ip}
    try:
        return {"ip": request.ip, "neighbors": discover_neighbors(config)}
    except SNMPUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha na descoberta: {exc}")


@router.post("/api/projetos/{projeto_id}/descobrir-cabos")
def descobrir_cabos(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    """Asks every SNMPv3 device of the map for its LLDP/CDP neighbors and suggests the cables."""
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Mapa não encontrado")
    equipamentos = [e for e in projeto.equipamentos if e.tipo not in ("Rack", "Atalho de mapa")]
    alvos = []
    for e in equipamentos:
        if e.monitor_mode == "snmpv3" and e.ip and e.ip != "Sem IP":
            config = abrir_config(e.monitor_config)
            if config.get("username"):
                alvos.append((e.id, {**config, "host": e.ip}))
    if not alvos:
        raise HTTPException(status_code=400, detail="Nenhum equipamento deste mapa é monitorado por SNMPv3: configure o SNMPv3 nos switches primeiro.")
    try:
        snmp_service._hlapi()
    except _SemSnmp as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    vizinhos, erros = cabos_lldp.consultar(alvos, snmp_service.discover_neighbors)
    conexoes = [(c.source, c.target) for c in db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id)]
    sugestoes, fora = cabos_lldp.sugerir([{"id": e.id, "nome": e.nome, "ip": e.ip} for e in equipamentos], conexoes, vizinhos)
    nomes = {e.id: e.nome for e in equipamentos}
    logger.info("%s: LLDP/CDP em %d equipamento(s) do mapa %s: %d cabo(s) sugerido(s)", user.username, len(alvos), projeto_id, len(sugestoes))
    return {
        "consultados": [{"id": eq_id, "nome": nomes.get(eq_id), "vizinhos": len(vizinhos.get(eq_id) or []), "erro": erros.get(eq_id)}
                        for eq_id, _ in alvos],
        "sugestoes": sugestoes, "fora_do_mapa": fora,
    }


# --- DESCOBERTA DA REDE (varredura de faixa) ---
class VarreduraIn(BaseModel):
    faixa: str


def _job_publico(db: Session, job):
    # Marca IPs que já estão em algum mapa (para não duplicar).
    no_mapa = {}
    for eq in db.query(models.Equipamento).filter(models.Equipamento.ip.in_([r["ip"] for r in job["resultados"]])).all():
        no_mapa.setdefault(eq.ip, set()).add(eq.projeto.nome if eq.projeto else "?")
    return {
        "id": job["id"], "status": job["status"], "fase": job["fase"], "total": job["total"], "verificados": job["verificados"],
        "erro": job["erro"], "duracao_s": round((job["fim"] or time.time()) - job["inicio"], 1),
        "resultados": [{**r, "no_mapa": sorted(no_mapa.get(r["ip"], []))} for r in job["resultados"]],
    }


@router.post("/api/descoberta")
def iniciar_descoberta(dados: VarreduraIn, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    try:
        ips = descoberta.validar_faixa(dados.faixa)
        job = descoberta.iniciar(ips, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    logger.info("%s iniciou varredura de %s (%d endereços)", user.username, dados.faixa, len(ips))
    return _job_publico(db, job)


@router.get("/api/descoberta/{job_id}")
def status_descoberta(job_id: str, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    job = descoberta.obter(job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Varredura não encontrada.")
    return _job_publico(db, job)


@router.delete("/api/descoberta/{job_id}")
def cancelar_descoberta(job_id: str, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    job = descoberta.cancelar(job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Varredura não encontrada.")
    return _job_publico(db, job)


# --- FUNÇÃO DE PING (TCP + ICMP com medição de tempo) ---
@router.get("/api/ping/{ip}")
def ping_rota(ip: str, user: models.Usuario = Depends(requer_editor)):
    # Exige login: sem isso qualquer pessoa usaria o servidor para varrer a rede interna.
    return ping_equipamento(ip)
