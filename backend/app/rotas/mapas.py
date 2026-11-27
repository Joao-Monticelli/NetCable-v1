"""Maps: projects, devices and cables, models, public links, status page, maintenance, acknowledgements, history and SLA."""

from ..relogio import utcnow
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import time
import re
import json
import secrets
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from .. import models, crud, alerts
from .. import backup, regras_alerta, monitor_http, auditoria
from fastapi import UploadFile, File
from fastapi.responses import Response
import csv
import io
import zipfile
from ..nucleo import (
    HISTORY_RETENTION_DAYS,
    HORARIO_RE,
    MONITOR_INTERVAL,
    VERSAO,
    abrir_config,
    get_current_user,
    get_db,
    get_fuso,
    iso_utc,
    logger,
    proteger_config,
    requer_editor,
)
from ..monitoramento import (
    SNMP_METRICS_INTERVAL,
    _http,
    _metricas,
    _metricas_compactas,
    _offline_desde,
    _ultimo_ciclo,
    enviar_alertas,
    get_limites,
)
from fastapi import APIRouter

router = APIRouter()


# --- PROJETOS ---
@router.get("/api/projetos")
def listar_projetos(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    return crud.resumo_projetos(db)


@router.post("/api/projetos")
def novo_projeto(nome: str, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.criar_projeto(db, nome, user.id)
    auditoria.registrar(db, user, "mapa.criado", projeto.nome, request, projeto.id)
    return {"id": projeto.id, "nome": projeto.nome}


@router.put("/api/projetos/{projeto_id}")
def editar_nome_projeto(projeto_id: int, novo_nome: str, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    anterior = crud.get_projeto(db, projeto_id)
    nome_anterior = anterior.nome if anterior else None
    projeto = crud.atualizar_projeto_nome(db, projeto_id, novo_nome)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    auditoria.registrar(db, user, "mapa.renomeado", f"{nome_anterior} -> {projeto.nome}", request, projeto_id)
    return {"id": projeto.id, "nome": projeto.nome}


@router.delete("/api/projetos/{projeto_id}")
def deletar_projeto_rota(projeto_id: int, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.get_projeto(db, projeto_id)
    nome = projeto.nome if projeto else None
    if crud.deletar_projeto(db, projeto_id):
        auditoria.registrar(db, user, "mapa.excluido", nome, request, projeto_id)
        return {"status": "sucesso"}
    raise HTTPException(status_code=404, detail="Projeto não encontrado")


# --- EXPORTAR / IMPORTAR MAPAS ---
LIMITE_IMPORTACAO = 50 * 1024 * 1024


@router.get("/api/projetos/{projeto_id}/exportar")
def exportar_projeto_rota(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return backup.exportar_projeto(db, projeto, abrir_config, VERSAO)


@router.post("/api/projetos/importar")
async def importar_projeto_rota(request: Request, arquivo: UploadFile = File(...), db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    conteudo = await arquivo.read(LIMITE_IMPORTACAO + 1)
    if len(conteudo) > LIMITE_IMPORTACAO:
        raise HTTPException(status_code=413, detail="Arquivo grande demais.")
    try:
        importados = backup.importar_arquivo(db, conteudo, user.id, proteger_config)
    except (ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile) as exc:
        legivel = isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError)
        detalhe = str(exc) if legivel else "Arquivo de mapa inválido."
        raise HTTPException(status_code=400, detail=detalhe)
    logger.info("%s importou %d mapa(s)", user.username, len(importados))
    auditoria.registrar(db, user, "mapa.importado", ", ".join(str(i.get("nome", i)) if isinstance(i, dict) else str(i) for i in importados), request)
    return {"importados": importados}


class EquipamentoCreate(BaseModel):
    id: str; nome: str; ip: str; tipo: str; status: str
    pingTime: Optional[float] = None; posX: float; posY: float; width: float; height: float
    monitorMode: str = "ip"; monitorConfig: Optional[dict] = None
    notificar: bool = True
    statusPublico: bool = True
    rackId: Optional[str] = None; rackU: Optional[int] = None; alturaU: Optional[int] = None
    modeloId: Optional[int] = None
    dependeDe: Optional[str] = None
    mapaDestinoId: Optional[int] = None


class ConexaoCreate(BaseModel):
    id: str; source: str; target: str; label: Optional[str] = None
    sourceHandle: Optional[str] = None; targetHandle: Optional[str] = None


class MapaSchema(BaseModel):
    equipamentos: List[EquipamentoCreate]
    conexoes: List[ConexaoCreate]


def mesclar_config_snmp(eq, config_anterior_cifrada):
    """O frontend nunca recebe as senhas SNMP de volta; senha vazia significa
    "manter a atual". Mescla com a config anterior e devolve cifrado."""
    config = eq.get('monitorConfig') or {}
    if eq.get('monitorMode') != 'snmpv3':
        return proteger_config(config) if config else None
    anterior = abrir_config(config_anterior_cifrada)
    mesclada = {**anterior, **{k: v for k, v in config.items() if v not in (None, "")}}
    return proteger_config(mesclada)


@router.post("/api/projetos/{projeto_id}/salvar")
def salvar_projeto(projeto_id: int, mapa: MapaSchema, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    configs_anteriores = {eq.id: eq.monitor_config for eq in projeto.equipamentos}
    eq_dict = [eq.model_dump() for eq in mapa.equipamentos]
    ids_mapa = {eq['id'] for eq in eq_dict}
    projetos_existentes = {p.id for p in crud.get_projetos(db)}
    for eq in eq_dict:
        # Atalho só pode apontar para outro mapa que existe.
        if eq.get('mapaDestinoId') not in projetos_existentes or eq.get('mapaDestinoId') == projeto_id:
            eq['mapaDestinoId'] = None
        if eq.get('monitorMode') == 'http':
            try:
                monitor_http.validar_url(monitor_http.montar_url(eq.get('ip'), eq.get('monitorConfig')))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"{eq.get('nome')}: URL inválida (use http:// ou https://).")
        eq['monitorConfig'] = mesclar_config_snmp(eq, configs_anteriores.get(eq['id']))
        # Uplink precisa ser outro equipamento deste mesmo mapa.
        if eq.get('dependeDe') not in ids_mapa or eq.get('dependeDe') == eq['id']:
            eq['dependeDe'] = None
    erro = crud.validar_racks(eq_dict)
    if erro:
        raise HTTPException(status_code=400, detail=erro)
    conn_dict = [conn.model_dump() for conn in mapa.conexoes]
    result = crud.salvar_mapa(db, projeto_id, eq_dict, conn_dict)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    auditoria.registrar(db, user, "mapa.salvo", f"{projeto.nome}: {len(eq_dict)} device(s), {len(conn_dict)} cable(s)", request, projeto_id)
    return result


class EquipamentoBase(BaseModel):
    id: str; nome: str; ip: str; tipo: str; status: str
    ping_time: Optional[float] = None; pos_x: float; pos_y: float; width: float; height: float
    monitor_mode: str = "ip"; monitor_config: Optional[dict] = None
    notificar: bool = True
    status_publico: bool = True
    rack_id: Optional[str] = None; rack_u: Optional[int] = None; altura_u: Optional[int] = None
    modelo_id: Optional[int] = None
    depende_de: Optional[str] = None
    mapa_destino_id: Optional[int] = None
    resumo_mapa: Optional[dict] = None  # atalho: online/offline do mapa de destino
    inalcancavel_por: Optional[str] = None  # uplink offline que explica a queda
    manutencao_ate: Optional[str] = None
    reconhecido: Optional[dict] = None  # who acknowledged the alert of this offline device
    snmp: Optional[dict] = None  # métricas SNMP compactas (CPU, memória, temperatura, portas)
    http: Optional[dict] = None  # last HTTP(S) check: status code, error, certificate
    model_config = ConfigDict(from_attributes=True)


class ConexaoBase(BaseModel):
    id: str; source: str; target: str; label: Optional[str] = None
    source_handle: Optional[str] = None; target_handle: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ModeloBase(BaseModel):
    id: int; nome: str; fabricante: Optional[str] = None; tipo: str
    altura_u: int; portas_rj45: int; portas_sfp: int; prefixo_porta: str = ""
    model_config = ConfigDict(from_attributes=True)


class ProjetoResponse(BaseModel):
    id: int; nome: str
    equipamentos: List[EquipamentoBase]; conexoes: List[ConexaoBase]
    modelos: List[ModeloBase] = []  # modelos usados neste mapa
    manutencao_ate: Optional[str] = None  # manutenção do projeto inteiro
    model_config = ConfigDict(from_attributes=True)


def _obter_dados_projeto(projeto_id: int, db: Session, projeto, publico: bool = False):
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    conexoes = db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).all()
    extras = _estado_alertas(db, projeto_id, projeto.equipamentos)
    equipamentos = []
    for equipamento in projeto.equipamentos:
        item = {column: getattr(equipamento, column) for column in ('id', 'nome', 'ip', 'tipo', 'status', 'ping_time', 'pos_x', 'pos_y', 'width', 'height', 'monitor_mode', 'notificar', 'status_publico', 'rack_id', 'rack_u', 'altura_u', 'modelo_id', 'depende_de', 'mapa_destino_id')}
        item.update(extras["por_equipamento"].get(equipamento.id, {}))
        config = abrir_config(equipamento.monitor_config)
        item['monitor_config'] = {} if publico else {key: value for key, value in config.items() if key not in ('authPassword', 'privPassword')}
        equipamentos.append(item)
    ids_modelos = {eq.modelo_id for eq in projeto.equipamentos if eq.modelo_id}
    modelos_usados = [m for m in crud.listar_modelos(db) if m.id in ids_modelos]
    return {"id": projeto.id, "nome": projeto.nome, "equipamentos": equipamentos, "conexoes": conexoes, "modelos": modelos_usados,
            "manutencao_ate": extras["manutencao_ate"]}


@router.get("/api/projetos/{projeto_id}/dados", response_model=ProjetoResponse)
def obter_dados_projeto(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return _obter_dados_projeto(projeto_id, db, projeto)


# --- BIBLIOTECA DE MODELOS DE EQUIPAMENTO ---
class ModeloIn(BaseModel):
    nome: str
    fabricante: Optional[str] = None
    tipo: str
    altura_u: int = 1
    portas_rj45: int = 0
    portas_sfp: int = 0
    prefixo_porta: str = ""


def _validar_modelo(dados: ModeloIn):
    nome = dados.nome.strip()
    if not 2 <= len(nome) <= 60:
        raise HTTPException(status_code=400, detail="O nome do modelo precisa ter de 2 a 60 caracteres.")
    if dados.tipo == "Rack":
        raise HTTPException(status_code=400, detail="Rack não é um modelo de equipamento.")
    if not 1 <= dados.altura_u <= 8:
        raise HTTPException(status_code=400, detail="Altura deve ser de 1U a 8U.")
    # Cabem até 2 fileiras de 24 portas RJ45 por U na frente desenhada.
    if not 0 <= dados.portas_rj45 <= 48 * dados.altura_u:
        raise HTTPException(status_code=400, detail=f"Para {dados.altura_u}U, use de 0 a {48 * dados.altura_u} portas RJ45.")
    if not 0 <= dados.portas_sfp <= 8:
        raise HTTPException(status_code=400, detail="Use de 0 a 8 portas SFP.")
    if len(dados.prefixo_porta) > 12:
        raise HTTPException(status_code=400, detail="Prefixo das portas muito longo (máx. 12).")
    return {**dados.model_dump(), "nome": nome, "fabricante": (dados.fabricante or "").strip() or None, "prefixo_porta": dados.prefixo_porta.strip()}


@router.get("/api/modelos", response_model=List[ModeloBase])
def listar_modelos(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    return crud.listar_modelos(db)


@router.post("/api/modelos", response_model=ModeloBase)
def criar_modelo(dados: ModeloIn, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    valores = _validar_modelo(dados)
    if crud.get_modelo_por_nome(db, valores["nome"]):
        raise HTTPException(status_code=400, detail="Já existe um modelo com esse nome.")
    return crud.salvar_modelo(db, valores)


@router.put("/api/modelos/{modelo_id}", response_model=ModeloBase)
def atualizar_modelo(modelo_id: int, dados: ModeloIn, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    valores = _validar_modelo(dados)
    existente = crud.get_modelo_por_nome(db, valores["nome"])
    if existente and existente.id != modelo_id:
        raise HTTPException(status_code=400, detail="Já existe um modelo com esse nome.")
    modelo = crud.salvar_modelo(db, valores, modelo_id)
    if not modelo:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    return modelo


@router.delete("/api/modelos/{modelo_id}")
def excluir_modelo(modelo_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    em_uso = crud.uso_do_modelo(db, modelo_id)
    if em_uso:
        raise HTTPException(status_code=400, detail=f"Modelo em uso por {em_uso} equipamento(s). Troque o modelo deles antes de excluir.")
    if not crud.deletar_modelo(db, modelo_id):
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    return {"status": "sucesso"}


# --- LINK PÚBLICO (token aleatório, revogável) ---
@router.get("/api/projetos/{projeto_id}/compartilhar")
def status_compartilhamento(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"token": projeto.share_token}


@router.post("/api/projetos/{projeto_id}/compartilhar")
def gerar_link_publico(projeto_id: int, request: Request, regenerar: bool = False, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    if projeto.share_token and not regenerar:
        return {"token": projeto.share_token}
    projeto = crud.definir_share_token(db, projeto_id, secrets.token_urlsafe(24))
    auditoria.registrar(db, user, "link.regenerado" if regenerar else "link.criado", projeto.nome, request, projeto_id)
    return {"token": projeto.share_token}


@router.delete("/api/projetos/{projeto_id}/compartilhar")
def revogar_link_publico(projeto_id: int, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.definir_share_token(db, projeto_id, None)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    auditoria.registrar(db, user, "link.revogado", projeto.nome, request, projeto_id)
    return {"status": "sucesso"}


# --- PÁGINA DE STATUS PÚBLICA (token próprio: sem IPs nem topologia) ---
@router.get("/api/projetos/{projeto_id}/status-publico")
def status_pagina_publica(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"token": projeto.status_token}


@router.post("/api/projetos/{projeto_id}/status-publico")
def gerar_pagina_publica(projeto_id: int, request: Request, regenerar: bool = False, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    if projeto.status_token and not regenerar:
        return {"token": projeto.status_token}
    projeto = crud.definir_status_token(db, projeto_id, secrets.token_urlsafe(24))
    _cache_status.clear()
    auditoria.registrar(db, user, "status.regenerado" if regenerar else "status.criado", projeto.nome, request, projeto_id)
    return {"token": projeto.status_token}


@router.delete("/api/projetos/{projeto_id}/status-publico")
def revogar_pagina_publica(projeto_id: int, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.definir_status_token(db, projeto_id, None)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    _cache_status.clear()
    auditoria.registrar(db, user, "status.revogado", projeto.nome, request, projeto_id)
    return {"status": "sucesso"}


STATUS_DIAS = 90


STATUS_CACHE_S = 30  # public and unauthenticated: computed at most every 30 s per page


_cache_status = {}


def montar_pagina_status(db: Session, projeto, agora=None):
    agora = agora or utcnow()
    fuso = get_fuso(db)
    equipamentos = [e for e in projeto.equipamentos if e.status_publico and crud._monitoravel(e) and e.ip and e.ip != "Sem IP"
                    and e.tipo not in ("Rack", "Atalho de mapa")]
    projetos_mnt, eqs_mnt = regras_alerta.manutencoes_ativas(db, agora, fuso)
    mapa_em_manutencao = projeto.id in projetos_mnt
    servicos = []
    for e in sorted(equipamentos, key=lambda x: (x.nome or "").lower()):
        diario = crud.disponibilidade_diaria(db, e.id, STATUS_DIAS, fuso, agora)
        janela = lambda n: [p for _, p in diario[-n:] if p is not None]
        media = lambda n: round(sum(janela(n)) / len(janela(n)), 2) if janela(n) else None
        manutencao = mapa_em_manutencao or e.id in eqs_mnt
        servicos.append({
            "nome": e.nome, "tipo": e.tipo,
            "status": "manutencao" if manutencao and e.status != "online" else e.status,
            "em_manutencao": manutencao,
            "uptime": {"1d": diario[-1][1], "30d": media(30), "90d": media(90)},
            "dias": [{"data": d.isoformat(), "pct": p} for d, p in diario],
        })
    nomes = {e.id: e.nome for e in equipamentos}
    from .incidentes import incidentes_da_pagina  # here: rotas.incidentes imports this module
    lista_incidentes = incidentes_da_pagina(db, projeto.id, nomes, agora)
    abertos = [i for i in lista_incidentes if i["estado"] != "resolvido"]
    fora = [s for s in servicos if s["status"] == "offline"]
    if fora:
        geral = "fora" if len(fora) == len(servicos) else "parcial"
    elif any(i["impacto"] == "grave" for i in abertos):
        geral = "parcial"
    elif abertos:
        geral = "incidente"
    elif any(s["em_manutencao"] for s in servicos) or mapa_em_manutencao:
        geral = "manutencao"
    else:
        geral = "operacional"
    proximas = []
    for m in regras_alerta.listar_manutencoes(db, projeto.id, agora):
        if m.equipamento_id and m.equipamento_id not in nomes:
            continue  # device not on the status page
        info = manutencao_publica(m, agora, fuso)
        base = {"alvo": nomes.get(m.equipamento_id), "motivo": m.motivo, "recorrencia": info["recorrencia"]}
        if info["ativa"]:
            proximas.append({**base, "ativa": True, "inicio": None, "ate": info["ativa_ate"]})
        elif info["proxima"] and datetime.fromisoformat(info["proxima"].rstrip("Z")) < agora + timedelta(days=14):
            proximas.append({**base, "ativa": False, "inicio": info["proxima"], "ate": None if info["recorrencia"] else info["ate"]})
    return {"titulo": projeto.nome, "atualizado_em": iso_utc(agora), "geral": geral, "fuso": getattr(fuso, "key", "UTC"),
            "dias_historico": HISTORY_RETENTION_DAYS, "servicos": servicos, "manutencoes": proximas,
            "incidentes": lista_incidentes}


@router.get("/api/public/status/{token}")
def pagina_status_publica(token: str, db: Session = Depends(get_db)):
    agora_m = time.monotonic()
    guardado = _cache_status.get(token)
    if guardado and agora_m - guardado[0] < STATUS_CACHE_S:
        return guardado[1]
    projeto = crud.get_projeto_por_status_token(db, token)
    if not projeto:
        raise HTTPException(status_code=404, detail="Página de status inválida ou desativada")
    dados = montar_pagina_status(db, projeto)
    if len(_cache_status) > 200:
        _cache_status.clear()
    _cache_status[token] = (agora_m, dados)
    return dados


@router.get("/api/public/mapas/{token}/dados", response_model=ProjetoResponse)
def obter_dados_projeto_publico(token: str, db: Session = Depends(get_db)):
    projeto = crud.get_projeto_por_token(db, token)
    if not projeto:
        raise HTTPException(status_code=404, detail="Link inválido ou revogado")
    return _obter_dados_projeto(projeto.id, db, projeto, publico=True)


# --- HISTÓRICO, STATUS E MÉTRICAS ---
@router.get("/api/projetos/{projeto_id}/historico")
def historico_projeto(projeto_id: int, limite: int = 100, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    limite = max(1, min(limite, 500))
    historico = crud.get_historico(db, projeto_id, limite)
    if historico is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return [{
        "equipamento_id": item.equipamento_id,
        "equipamento_nome": nome,
        "status": item.status,
        "tempo_ms": item.tempo_ms,
        "criado_em": iso_utc(item.criado_em),
    } for item, nome in historico]


@router.get("/api/projetos/{projeto_id}/status")
def status_projeto(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Status atual de cada equipamento, mantido pelo monitor do backend.
    O Editor consulta esta rota em vez de pingar cada equipamento."""
    linhas = crud.get_status_projeto(db, projeto_id)
    if linhas is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    extras = _estado_alertas(db, projeto_id)
    return {
        "monitor_ativo": MONITOR_INTERVAL > 0,
        "ultimo_ciclo": iso_utc(_ultimo_ciclo["fim"]),
        "manutencao_ate": extras["manutencao_ate"],
        "equipamentos": [{"id": eq_id, "status": status, "ping_time": ping, **extras["por_equipamento"].get(eq_id, {})}
                         for eq_id, status, ping in linhas],
    }


def _estado_alertas(db: Session, projeto_id: int, equipamentos=None):
    """Inalcançáveis (uplink offline) e janelas de manutenção ativas de um projeto."""
    if equipamentos is None:
        equipamentos = db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).all()
    projetos, por_eq = regras_alerta.manutencoes_ativas(db)
    reconhecidos = regras_alerta.reconhecimentos(db, projeto_id)
    extras = {}
    for eq_id, causa in regras_alerta.inalcancaveis(equipamentos).items():
        extras.setdefault(eq_id, {})["inalcancavel_por"] = causa
    for e in equipamentos:
        if e.id in por_eq:
            extras.setdefault(e.id, {})["manutencao_ate"] = iso_utc(por_eq[e.id])
        if e.id in reconhecidos:
            r = reconhecidos[e.id]
            extras.setdefault(e.id, {})["reconhecido"] = {"usuario": r.usuario, "nota": r.nota, "em": iso_utc(r.criado_em)}
        if e.id in _metricas:
            extras.setdefault(e.id, {})["snmp"] = _metricas_compactas(_metricas[e.id])
        if e.id in _http and e.monitor_mode == "http":
            extras.setdefault(e.id, {})["http"] = _http[e.id]
    atalhos = [e for e in equipamentos if e.mapa_destino_id]
    if atalhos:
        resumos = crud.resumo_por_projeto(db, [e.mapa_destino_id for e in atalhos])
        for e in atalhos:
            extras.setdefault(e.id, {})["resumo_mapa"] = resumos.get(e.mapa_destino_id) or {"id": e.mapa_destino_id, "removido": True}
    return {"manutencao_ate": iso_utc(projetos.get(projeto_id)), "por_equipamento": extras}


class RecorrenciaIn(BaseModel):
    dias: List[int]                     # 0 = Monday ... 6 = Sunday
    hora: str                           # HH:MM in the system time zone
    minutos: int                        # duration of each occurrence


class ManutencaoIn(BaseModel):
    horas: Optional[float] = None       # duração (a partir de agora ou do início)
    ate: Optional[datetime] = None      # ou um horário final (ISO); na semanal: até quando a regra vale
    inicio: Optional[datetime] = None   # agendada: começa neste horário (ISO)
    recorrencia: Optional[RecorrenciaIn] = None  # semanal
    equipamento_id: Optional[str] = None
    motivo: Optional[str] = None


def _utc(momento):
    if momento is None:
        return None
    return momento.astimezone(timezone.utc).replace(tzinfo=None) if momento.tzinfo else momento


def manutencao_publica(m, agora=None, fuso=None):
    agora = agora or utcnow()
    rec = regras_alerta.ler_recorrencia(m)
    fim_atual = regras_alerta.fim_se_ativa(m, agora, fuso)
    if rec:
        proxima = regras_alerta.proxima_ocorrencia(rec, max(agora, m.inicio or agora), fuso)
        proxima = proxima if proxima and proxima < m.ate else None
        rec = {k: rec[k] for k in ("dias", "hora", "minutos")}
    else:
        proxima = m.inicio if m.inicio and m.inicio > agora else None
    return {
        "id": m.id, "equipamento_id": m.equipamento_id, "inicio": iso_utc(m.inicio), "motivo": m.motivo,
        "ate": None if m.ate >= regras_alerta.SEM_FIM else iso_utc(m.ate), "recorrencia": rec,
        "ativa": fim_atual is not None, "ativa_ate": iso_utc(fim_atual), "proxima": iso_utc(proxima),
    }


@router.get("/api/projetos/{projeto_id}/manutencao")
def listar_manutencao(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    if not crud.get_projeto(db, projeto_id):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    agora, fuso = utcnow(), get_fuso(db)
    return [manutencao_publica(m, agora, fuso) for m in regras_alerta.listar_manutencoes(db, projeto_id, agora)]


@router.post("/api/projetos/{projeto_id}/manutencao")
def iniciar_manutencao(projeto_id: int, dados: ManutencaoIn, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    if not crud.get_projeto(db, projeto_id):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    agora = utcnow()
    inicio, ate, recorrencia = _utc(dados.inicio), _utc(dados.ate), None
    if dados.recorrencia:
        r = dados.recorrencia
        dias = sorted(set(r.dias))
        if not dias or any(d < 0 or d > 6 for d in dias):
            raise HTTPException(status_code=400, detail="Escolha pelo menos um dia da semana.")
        if not HORARIO_RE.match(r.hora or ""):
            raise HTTPException(status_code=400, detail="Horário inválido (use HH:MM).")
        if not 5 <= r.minutos <= 24 * 60:
            raise HTTPException(status_code=400, detail="Cada janela semanal deve durar de 5 minutos a 24 horas.")
        recorrencia = {"dias": dias, "hora": r.hora, "minutos": r.minutos}
        ate = ate or regras_alerta.SEM_FIM
        if ate <= agora or (inicio and inicio >= ate):
            raise HTTPException(status_code=400, detail="A manutenção deve terminar no futuro e durar no máximo 30 dias.")
    else:
        base = inicio or agora
        if inicio and not agora - timedelta(minutes=5) <= inicio <= agora + timedelta(days=366):
            raise HTTPException(status_code=400, detail="O início deve ser no futuro (até 1 ano).")
        if not ate and dados.horas:
            ate = base + timedelta(hours=dados.horas)
        if not ate:
            raise HTTPException(status_code=400, detail="Informe a duração da manutenção.")
        if not (agora < ate and base < ate <= base + timedelta(days=30)):
            raise HTTPException(status_code=400, detail="A manutenção deve terminar no futuro e durar no máximo 30 dias.")
        if inicio and inicio <= agora:
            inicio = None  # starts now
    eq = None
    if dados.equipamento_id:
        eq = crud.get_equipamento(db, dados.equipamento_id)
        if not eq or eq.projeto_id != projeto_id:
            raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    m = regras_alerta.criar_manutencao(db, projeto_id, ate, dados.equipamento_id, (dados.motivo or "").strip()[:200] or None, user.id,
                                       inicio=inicio, recorrencia=recorrencia)
    alvo = eq.nome if eq else "*"
    if recorrencia or inicio:
        detalhe = f"{alvo}: weekly {recorrencia['dias']} {recorrencia['hora']} {recorrencia['minutos']} min" if recorrencia else f"{alvo}: {iso_utc(inicio)} -> {iso_utc(ate)}"
        auditoria.registrar(db, user, "manutencao.agendada", detalhe, request, projeto_id)
    else:
        logger.info("%s iniciou manutenção (projeto %s, equipamento %s) até %s", user.username, projeto_id, dados.equipamento_id, ate)
        auditoria.registrar(db, user, "manutencao.iniciada", f"{alvo} -> {iso_utc(ate)}", request, projeto_id)
    return manutencao_publica(m, agora, get_fuso(db))


@router.delete("/api/projetos/{projeto_id}/manutencao")
def encerrar_manutencao(projeto_id: int, request: Request, equipamento_id: Optional[str] = None, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    """Ends what is silencing the target now; scheduled and weekly windows stay (the current weekly one is skipped)."""
    if regras_alerta.cancelar_manutencao(db, projeto_id, equipamento_id):
        eq = crud.get_equipamento(db, equipamento_id) if equipamento_id else None
        auditoria.registrar(db, user, "manutencao.encerrada", eq.nome if eq else (equipamento_id or "*"), request, projeto_id)
    return {"status": "ok"}


@router.delete("/api/projetos/{projeto_id}/manutencao/{manutencao_id}")
def remover_manutencao(projeto_id: int, manutencao_id: int, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    m = regras_alerta.remover_manutencao(db, projeto_id, manutencao_id)
    if not m:
        raise HTTPException(status_code=404, detail="Manutenção não encontrada.")
    eq = crud.get_equipamento(db, m.equipamento_id) if m.equipamento_id else None
    auditoria.registrar(db, user, "manutencao.removida", eq.nome if eq else (m.equipamento_id or "*"), request, projeto_id)
    return {"status": "ok"}


# --- RECONHECER ALERTA ("estou vendo") ---
class ReconhecerIn(BaseModel):
    nota: Optional[str] = None


def _equipamento_do_projeto(db: Session, projeto_id: int, equipamento_id: str):
    eq = crud.get_equipamento(db, equipamento_id)
    if not eq or eq.projeto_id != projeto_id:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    return eq


@router.post("/api/projetos/{projeto_id}/equipamentos/{equipamento_id}/reconhecer")
def reconhecer_alerta(projeto_id: int, equipamento_id: str, dados: ReconhecerIn, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    eq = _equipamento_do_projeto(db, projeto_id, equipamento_id)
    if eq.status != "offline":
        raise HTTPException(status_code=400, detail="Só dá para reconhecer o alerta de um equipamento offline.")
    nota = (dados.nota or "").strip()[:200] or None
    r = regras_alerta.reconhecer(db, eq, user.username, nota)
    auditoria.registrar(db, user, "alerta.reconhecido", eq.nome + (f": {nota}" if nota else ""), request, projeto_id)
    # Tell the team (chat channels and e-mail), unless the device is in maintenance or muted.
    if eq.notificar and not regras_alerta.em_manutencao(eq, regras_alerta.manutencoes_ativas(db)):
        enviar_alertas(db, [alerts.montar_evento_reconhecido(eq, eq.projeto.nome if eq.projeto else None, user.username, nota)])
    return {"usuario": r.usuario, "nota": r.nota, "em": iso_utc(r.criado_em)}


@router.delete("/api/projetos/{projeto_id}/equipamentos/{equipamento_id}/reconhecer")
def desfazer_reconhecimento(projeto_id: int, equipamento_id: str, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    eq = _equipamento_do_projeto(db, projeto_id, equipamento_id)
    if regras_alerta.remover_reconhecimento(db, eq.id):
        auditoria.registrar(db, user, "alerta.reconhecimento_removido", eq.nome, request, projeto_id)
        estado = _offline_desde.get(eq.id)
        if estado:
            estado["aviso"] = time.monotonic()  # next reminder counts from now
    return {"status": "ok"}


@router.get("/api/projetos/{projeto_id}/disponibilidade")
def disponibilidade_projeto(projeto_id: int, horas: int = 24, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    horas = max(1, min(horas, 24 * 90))
    dados = crud.calcular_disponibilidade(db, projeto_id, horas)
    if dados is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"horas": horas, "equipamentos": dados}


@router.get("/api/projetos/{projeto_id}/equipamentos/{equipamento_id}/latencia")
def latencia_equipamento(projeto_id: int, equipamento_id: str, horas: int = 24, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    equipamento = crud.get_equipamento(db, equipamento_id)
    if not equipamento or equipamento.projeto_id != projeto_id:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    horas = max(1, min(horas, 24 * 90))
    pontos = crud.get_latencia(db, equipamento_id, horas)
    return {
        "equipamento_id": equipamento.id, "nome": equipamento.nome, "ip": equipamento.ip, "horas": horas,
        "pontos": [{"t": iso_utc(p.criado_em), "status": p.status, "ms": p.tempo_ms} for p in pontos],
    }


@router.get("/api/projetos/{projeto_id}/equipamentos/{equipamento_id}/metricas")
def metricas_equipamento(projeto_id: int, equipamento_id: str, horas: int = 24, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    equipamento = crud.get_equipamento(db, equipamento_id)
    if not equipamento or equipamento.projeto_id != projeto_id:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    horas = max(1, min(horas, 24 * 90))
    limite = utcnow() - timedelta(hours=horas)
    pontos = db.query(models.MetricaSnmp).filter(models.MetricaSnmp.equipamento_id == equipamento_id, models.MetricaSnmp.criado_em >= limite).order_by(models.MetricaSnmp.criado_em).all()
    return {
        "equipamento_id": equipamento.id, "nome": equipamento.nome, "ip": equipamento.ip, "horas": horas,
        "snmp": equipamento.monitor_mode == "snmpv3", "intervalo_s": SNMP_METRICS_INTERVAL,
        "atual": _metricas.get(equipamento_id), "limites": get_limites(db),
        "historico": [{"t": iso_utc(p.criado_em), "cpu": p.cpu_pct, "mem": p.memoria_pct, "temp": p.temperatura_c,
                       "in": p.in_bps, "out": p.out_bps} for p in pontos],
    }


# --- SLA REPORT (CSV) ---
def _duracao_legivel(segundos):
    segundos = int(round(segundos or 0))
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}"


@router.get("/api/projetos/{projeto_id}/sla.csv")
def sla_csv(projeto_id: int, dias: int = 30, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Availability of every monitored device in the period, as CSV (comma-separated, UTF-8 with BOM
    so Excel shows accents correctly). Limited by HISTORY_RETENTION_DAYS: older history is gone."""
    if not 1 <= dias <= 365:
        raise HTTPException(status_code=400, detail="Período inválido (use de 1 a 365 dias).")
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    agora = utcnow()
    itens = crud.calcular_disponibilidade(db, projeto_id, dias * 24, agora)
    saida = io.StringIO()
    w = csv.writer(saida)
    w.writerow(["map", "device", "ip", "type", "status_now", "availability_pct", "downtime_hms", "downtime_seconds",
                "outages", "avg_latency_ms", "monitored_hours", "period_start_utc", "period_end_utc"])
    tipos = {eq.id: eq.tipo for eq in projeto.equipamentos}
    inicio = agora - timedelta(days=dias)
    for item in sorted(itens, key=lambda i: (i["uptime_pct"] if i["uptime_pct"] is not None else 101, i["nome"] or "")):
        w.writerow([
            projeto.nome, item["nome"], item["ip"], tipos.get(item["equipamento_id"], ""), item["status"],
            "" if item["uptime_pct"] is None else f"{item['uptime_pct']:.3f}",
            _duracao_legivel(item["offline_s"]), int(round(item["offline_s"])), item["quedas"],
            "" if item["latencia_media_ms"] is None else item["latencia_media_ms"],
            round(item["monitorado_s"] / 3600, 2), iso_utc(inicio), iso_utc(agora),
        ])
    nome = re.sub(r"[^\w.-]+", "_", projeto.nome or "map")[:50]
    return Response("﻿" + saida.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="netcable-sla-{nome}-{dias}d.csv"'})
