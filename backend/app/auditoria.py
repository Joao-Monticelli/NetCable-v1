"""Audit log: who did what, and when (logins, users, maps, settings, backups, share links).

Entries never hold passwords or secrets, only what changed (e.g. "SMTP settings saved").
Old entries are removed after AUDIT_RETENTION_DAYS (default 365, 0 keeps them forever).
"""

from .relogio import utcnow
import logging
import os
from datetime import timedelta

from . import models

logger = logging.getLogger("netcable.auditoria")

AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "365"))
LIMITE_DETALHE = 500


def ip_de(request):
    if request is None or request.client is None:
        return None
    return request.client.host


def registrar(db, usuario, acao, detalhe=None, request=None, projeto_id=None):
    """Writes one entry. `usuario` is a Usuario or a username. Never raises: auditing must not
    break the action being audited."""
    nome = getattr(usuario, "username", usuario) or None
    try:
        db.add(models.Auditoria(
            usuario=str(nome)[:80] if nome else None, acao=acao[:60],
            detalhe=str(detalhe)[:LIMITE_DETALHE] if detalhe else None,
            ip=ip_de(request), projeto_id=projeto_id,
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not write audit entry %s", acao)


def listar(db, limite=200, usuario=None, acao=None, antes_de=None):
    q = db.query(models.Auditoria)
    if usuario:
        q = q.filter(models.Auditoria.usuario == usuario)
    if acao:
        q = q.filter(models.Auditoria.acao.like(f"{acao}%"))
    if antes_de:
        q = q.filter(models.Auditoria.id < antes_de)
    return q.order_by(models.Auditoria.id.desc()).limit(max(1, min(limite, 1000))).all()


def limpar(db, dias=AUDIT_RETENTION_DAYS, agora=None):
    if dias <= 0:
        return 0
    limite = (agora or utcnow()) - timedelta(days=dias)
    apagados = db.query(models.Auditoria).filter(models.Auditoria.criado_em < limite).delete(synchronize_session=False)
    db.commit()
    return apagados
