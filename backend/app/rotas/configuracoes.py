"""Admin settings: e-mail, alert channels, backups, SNMP thresholds and the audit log."""

from ..relogio import utcnow
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
import os
import re
from pydantic import BaseModel
from typing import Optional
from zoneinfo import ZoneInfo
from .. import models, crud, alerts, email_service
from ..i18n import traduzir, IDIOMAS
from .. import backup, auditoria
from fastapi.responses import FileResponse
from ..nucleo import (
    CAMPOS_CANAIS,
    CAMPOS_SECRETOS,
    FUSO_PADRAO,
    _canais_salvos,
    get_canais_config,
    get_db,
    get_smtp_config,
    iso_utc,
    proteger_config,
    requer_admin,
)
from ..monitoramento import BACKUP_DIR_PADRAO, fazer_backup, get_backup_config, get_lembrete_min, get_limites
from fastapi import APIRouter

router = APIRouter()


# --- CONFIGURAÇÃO DE E-MAIL (ADMIN) ---
class SmtpConfig(BaseModel):
    host: str = ""
    porta: int = 587
    seguranca: str = "starttls"
    usuario: str = ""
    senha: Optional[str] = None  # vazio/None mantém a senha atual
    remetente: str = ""
    fuso: Optional[str] = None


@router.get("/api/config/email")
def obter_config_email(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    smtp = get_smtp_config(db)
    fuso = crud.get_configuracoes(db, "sistema.fuso").get("sistema.fuso") or FUSO_PADRAO
    return {
        "host": smtp.get("host") or "", "porta": int(smtp.get("porta") or 587),
        "seguranca": smtp.get("seguranca") or "starttls", "usuario": smtp.get("usuario") or "",
        "remetente": smtp.get("remetente") or "", "senha_definida": bool(smtp.get("senha")),
        "fuso": fuso, "configurado": email_service.smtp_configurado(smtp),
    }


@router.put("/api/config/email")
def salvar_config_email(dados: SmtpConfig, request: Request, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    if dados.seguranca not in email_service.SEGURANCAS:
        raise HTTPException(status_code=400, detail="Segurança inválida (use starttls, ssl ou nenhuma).")
    if not 1 <= dados.porta <= 65535:
        raise HTTPException(status_code=400, detail="Porta inválida.")
    if dados.fuso:
        try:
            ZoneInfo(dados.fuso)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Fuso horário desconhecido: {dados.fuso}")
    valores = {
        "smtp.host": dados.host.strip(), "smtp.porta": str(dados.porta), "smtp.seguranca": dados.seguranca,
        "smtp.usuario": dados.usuario.strip(), "smtp.remetente": dados.remetente.strip(),
    }
    if dados.senha:
        valores["smtp.senha"] = proteger_config({"senha": dados.senha})
    if dados.fuso:
        valores["sistema.fuso"] = dados.fuso
    crud.salvar_configuracoes(db, valores)
    auditoria.registrar(db, admin, "config.email", f"{dados.host.strip() or '-'}:{dados.porta}" + (" (password changed)" if dados.senha else ""), request)
    return obter_config_email(db, admin)


class EmailTeste(BaseModel):
    destinatario: Optional[str] = None


@router.post("/api/config/email/teste")
def testar_email(dados: EmailTeste, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    destino = (dados.destinatario or admin.email or "").strip()
    if not destino:
        raise HTTPException(status_code=400, detail="Informe um destinatário ou cadastre um e-mail no seu perfil.")
    try:
        email_service.enviar_email(
            get_smtp_config(db), [destino], traduzir("[NetCable] E-mail de teste", admin.idioma),
            traduzir("Se você recebeu esta mensagem, o envio de e-mails do NetCable está funcionando.", admin.idioma),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha no envio: {exc}")
    return {"status": "enviado", "para": destino}


class CanaisIn(BaseModel):
    # Campos secretos: None mantém o valor atual; "" apaga.
    telegram_token: Optional[str] = None
    telegram_chat: Optional[str] = None
    discord_url: Optional[str] = None
    ntfy_url: Optional[str] = None
    ntfy_token: Optional[str] = None
    webhook_url: Optional[str] = None
    idioma: Optional[str] = None
    lembrete_min: Optional[int] = None  # repeat "still offline" every N minutes until acknowledged (0 = off)


@router.get("/api/config/alertas")
def obter_canais(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    salvos, ambiente, efetivo = _canais_salvos(db), alerts.canais_do_ambiente(), get_canais_config(db)
    resposta = {"idioma": efetivo["idioma"] or "en", "ativos": alerts.canais_configurados(None, efetivo), "lembrete_min": get_lembrete_min(db)}
    for campo in CAMPOS_CANAIS:
        if campo in CAMPOS_SECRETOS:
            resposta[f"{campo}_definido"] = bool(salvos[campo])
        else:
            resposta[campo] = salvos[campo]
        resposta[f"{campo}_ambiente"] = bool(ambiente.get(campo)) and not salvos[campo]
    return resposta


@router.put("/api/config/alertas")
def salvar_canais(dados: CanaisIn, request: Request, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    valores = {}
    for campo in CAMPOS_CANAIS:
        valor = getattr(dados, campo)
        if valor is None:
            continue
        valor = valor.strip()
        if campo.endswith("_url") and valor and not re.match(r"^https?://", valor, re.I):
            raise HTTPException(status_code=400, detail="Use um endereço que comece com http:// ou https://.")
        valores[f"alertas.{campo}"] = proteger_config({"v": valor}) if (valor and campo in CAMPOS_SECRETOS) else valor
    if dados.idioma is not None:
        if dados.idioma not in IDIOMAS:
            raise HTTPException(status_code=400, detail="Idioma inválido (use en ou pt).")
        valores["alertas.idioma"] = dados.idioma
    if dados.lembrete_min is not None:
        if dados.lembrete_min != 0 and not 5 <= dados.lembrete_min <= 1440:
            raise HTTPException(status_code=400, detail="O lembrete deve ser de 5 a 1440 minutos (0 desliga).")
        valores["alertas.lembrete_min"] = str(dados.lembrete_min)
    crud.salvar_configuracoes(db, valores)
    alterados = sorted({c.split(".", 1)[1].split("_")[0] for c in valores if c != "alertas.idioma"})
    auditoria.registrar(db, admin, "config.alertas", ", ".join(alterados) or None, request)
    return obter_canais(db, admin)


class CanalTeste(BaseModel):
    canal: str


@router.post("/api/config/alertas/teste")
def testar_canal(dados: CanalTeste, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    cfg = get_canais_config(db)
    if not alerts.canais_configurados(None, cfg).get(dados.canal):
        raise HTTPException(status_code=400, detail="Canal não configurado.")
    try:
        alerts.testar_canal(dados.canal, cfg)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha no envio: {alerts.erro_seguro(exc, cfg)}")
    return {"status": "enviado"}


class BackupConfigIn(BaseModel):
    ativo: bool = True
    diretorio: Optional[str] = None
    horario: str = "03:00"
    manter: int = 7


@router.get("/api/backup")
def obter_backup(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    cfg = get_backup_config(db)
    return {**cfg, "diretorio_padrao": BACKUP_DIR_PADRAO, "arquivos": backup.listar_backups(cfg["diretorio"])}


@router.put("/api/backup")
def salvar_backup_config(dados: BackupConfigIn, request: Request, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", dados.horario or ""):
        raise HTTPException(status_code=400, detail="Horário inválido (use HH:MM).")
    if not 1 <= dados.manter <= 365:
        raise HTTPException(status_code=400, detail="Quantidade de backups deve ser entre 1 e 365.")
    diretorio = (dados.diretorio or "").strip() or BACKUP_DIR_PADRAO
    if not os.path.isabs(diretorio):
        raise HTTPException(status_code=400, detail="Use um caminho absoluto para a pasta de backup.")
    try:
        backup.testar_diretorio(diretorio)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Não foi possível gravar na pasta: {exc}")
    crud.salvar_configuracoes(db, {
        "backup.ativo": "1" if dados.ativo else "0",
        "backup.diretorio": "" if diretorio == BACKUP_DIR_PADRAO else diretorio,
        "backup.horario": dados.horario, "backup.manter": str(dados.manter),
    })
    auditoria.registrar(db, admin, "config.backup", f"{'on' if dados.ativo else 'off'} {dados.horario}, keep {dados.manter}, {diretorio}", request)
    return obter_backup(db, admin)


@router.post("/api/backup/agora")
def backup_agora(request: Request, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    try:
        caminho = fazer_backup(db)
    except Exception as exc:
        crud.salvar_configuracoes(db, {"backup.ultimo_erro": f"{iso_utc(utcnow())} {exc}"})
        raise HTTPException(status_code=500, detail=f"Falha no backup: {exc}")
    auditoria.registrar(db, admin, "backup.criado", os.path.basename(caminho), request)
    return {"arquivo": os.path.basename(caminho), **obter_backup(db, admin)}


@router.get("/api/backup/arquivo/{nome}")
def baixar_backup(nome: str, request: Request, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    if not backup.PADRAO_ARQUIVO.match(nome):
        raise HTTPException(status_code=404, detail="Backup não encontrado")
    caminho = os.path.join(get_backup_config(db)["diretorio"], nome)
    if not os.path.isfile(caminho):
        raise HTTPException(status_code=404, detail="Backup não encontrado")
    auditoria.registrar(db, admin, "backup.baixado", nome, request)
    return FileResponse(caminho, media_type="application/zip", filename=nome)


class LimitesIn(BaseModel):
    temperatura: float = 75
    cpu: float = 95


@router.get("/api/config/metricas")
def obter_limites(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    return get_limites(db)


@router.put("/api/config/metricas")
def salvar_limites(dados: LimitesIn, request: Request, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    if not (0 <= dados.temperatura <= 150 and 0 <= dados.cpu <= 100):
        raise HTTPException(status_code=400, detail="Limites inválidos (temperatura 0–150 °C, CPU 0–100%; 0 desativa).")
    crud.salvar_configuracoes(db, {"metricas.limite_temp": str(dados.temperatura), "metricas.limite_cpu": str(dados.cpu)})
    auditoria.registrar(db, admin, "config.metricas", f"temp {dados.temperatura:g} °C, CPU {dados.cpu:g}%", request)
    return get_limites(db)


# --- AUDIT LOG (ADMIN) ---
@router.get("/api/auditoria")
def listar_auditoria(limite: int = 200, usuario: Optional[str] = None, acao: Optional[str] = None, antes_de: Optional[int] = None,
                     db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    itens = auditoria.listar(db, limite, usuario or None, acao or None, antes_de)
    return [{"id": a.id, "criado_em": iso_utc(a.criado_em), "usuario": a.usuario, "acao": a.acao, "detalhe": a.detalhe,
             "ip": a.ip, "projeto_id": a.projeto_id} for a in itens]
