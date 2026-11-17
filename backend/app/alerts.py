"""Envio de alertas de mudança de status (e-mail, Telegram e webhook).

Configuração:
  - E-mail: servidor SMTP definido pelo admin na interface; cada usuário escolhe
    no perfil se recebe os alertas. Só equipamentos com "notificar" ligado geram alerta.
  - ALERT_WEBHOOK_URL / ALERT_WEBHOOK_TIMEOUT: POST JSON por evento.
  - TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID: uma mensagem por ciclo de monitoramento.

Os eventos de um mesmo ciclo são agrupados (uma mensagem/e-mail só, mesmo que
vários equipamentos caiam juntos). O envio roda numa thread separada.
"""

import logging
import os
import threading
from datetime import datetime, timezone

import requests

from . import email_service

logger = logging.getLogger("netcable.alerts")

WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "").strip()
WEBHOOK_TIMEOUT = float(os.getenv("ALERT_WEBHOOK_TIMEOUT", "3"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def canais_configurados(smtp_cfg=None):
    return {
        "webhook": bool(WEBHOOK_URL),
        "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "email": email_service.smtp_configurado(smtp_cfg),
    }


def montar_evento(equipamento, projeto_nome, status, status_anterior, tempo_ms=None):
    return {
        "evento": "equipamento_offline" if status == "offline" else "equipamento_online",
        "projeto": projeto_nome,
        "equipamento": equipamento.nome,
        "ip": equipamento.ip,
        "status_anterior": status_anterior,
        "status": status,
        "tempo_ms": tempo_ms,
        "horario": datetime.now(timezone.utc).isoformat(),
    }


def formatar_mensagem(evento):
    if evento["status"] == "offline":
        titulo = "🔴 Equipamento OFFLINE"
    else:
        titulo = "🟢 Equipamento voltou ONLINE"
    linhas = [titulo, f"{evento['equipamento']} ({evento['ip']})"]
    if evento.get("projeto"):
        linhas.append(f"Mapa: {evento['projeto']}")
    if evento["status"] == "online" and evento.get("tempo_ms") is not None:
        linhas.append(f"Latência: {evento['tempo_ms']} ms")
    return "\n".join(linhas)


def _enviar(eventos, smtp_cfg, destinatarios):
    if WEBHOOK_URL:
        for evento in eventos:
            try:
                requests.post(WEBHOOK_URL, json=evento, timeout=WEBHOOK_TIMEOUT)
            except Exception as exc:
                logger.warning("Falha ao enviar alerta webhook: %s", exc)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": "\n\n".join(formatar_mensagem(e) for e in eventos)},
                timeout=WEBHOOK_TIMEOUT,
            )
        except Exception as exc:
            logger.warning("Falha ao enviar alerta Telegram: %s", exc)
    if destinatarios and email_service.smtp_configurado(smtp_cfg):
        try:
            assunto, texto, html = email_service.montar_email_alerta(eventos)
            email_service.enviar_email(smtp_cfg, destinatarios, assunto, texto, html)
        except Exception as exc:
            logger.warning("Falha ao enviar alerta por e-mail: %s", exc)


def notificar(eventos, smtp_cfg=None, destinatarios=None):
    """Envia os eventos (lista) por todos os canais configurados, em segundo plano."""
    if isinstance(eventos, dict):
        eventos = [eventos]
    if not eventos:
        return
    canais = canais_configurados(smtp_cfg)
    if not (canais["webhook"] or canais["telegram"] or (canais["email"] and destinatarios)):
        return
    threading.Thread(target=_enviar, args=(eventos, smtp_cfg, destinatarios), name="netcable-alerta", daemon=True).start()
