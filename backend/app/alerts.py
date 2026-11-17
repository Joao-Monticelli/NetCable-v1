"""Envio de alertas de mudança de status (webhook genérico e Telegram).

Configuração por variáveis de ambiente (nada é obrigatório):
  ALERT_WEBHOOK_URL       URL que recebe um POST JSON a cada queda/recuperação.
  ALERT_WEBHOOK_TIMEOUT   Timeout em segundos (padrão 3).
  TELEGRAM_BOT_TOKEN      Token do bot criado com o @BotFather.
  TELEGRAM_CHAT_ID        ID do chat/grupo que recebe as mensagens.

O envio acontece numa thread separada para não atrasar o ciclo de monitoramento.
"""

import logging
import os
import threading
from datetime import datetime, timezone

import requests

logger = logging.getLogger("netcable.alerts")

WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "").strip()
WEBHOOK_TIMEOUT = float(os.getenv("ALERT_WEBHOOK_TIMEOUT", "3"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def canais_configurados():
    return {"webhook": bool(WEBHOOK_URL), "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)}


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


def _enviar(evento):
    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json=evento, timeout=WEBHOOK_TIMEOUT)
        except Exception as exc:
            logger.warning("Falha ao enviar alerta webhook: %s", exc)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": formatar_mensagem(evento)},
                timeout=WEBHOOK_TIMEOUT,
            )
        except Exception as exc:
            logger.warning("Falha ao enviar alerta Telegram: %s", exc)


def notificar(evento):
    if not any(canais_configurados().values()):
        return
    threading.Thread(target=_enviar, args=(evento,), name="netcable-alerta", daemon=True).start()
