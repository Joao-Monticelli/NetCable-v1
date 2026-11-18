"""Envio de alertas de mudança de status (e-mail, Telegram, Discord, ntfy e webhook).

Configuração:
  - Canais: definidos pelo admin na interface (⚙️ → Canais de alerta). As variáveis de ambiente
    TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID / ALERT_WEBHOOK_URL / DISCORD_WEBHOOK_URL / NTFY_URL /
    NTFY_TOKEN / ALERT_LANGUAGE continuam valendo quando o campo na interface está vazio.
  - E-mail: servidor SMTP definido pelo admin; cada usuário escolhe no perfil se recebe os alertas.
    Só equipamentos com "notificar" ligado geram alerta.

Os eventos de um mesmo ciclo são agrupados (uma mensagem/e-mail só, mesmo que
vários equipamentos caiam juntos). O envio roda numa thread separada.
"""

import logging
import os
import threading
from datetime import datetime, timezone

import requests

from . import email_service
from .email_service import texto_dependentes
from .i18n import traduzir as tr, normalizar

logger = logging.getLogger("netcable.alerts")

WEBHOOK_TIMEOUT = float(os.getenv("ALERT_WEBHOOK_TIMEOUT", "5"))


def canais_do_ambiente():
    return {
        "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        "telegram_chat": os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        "discord_url": os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
        "ntfy_url": os.getenv("NTFY_URL", "").strip(),
        "ntfy_token": os.getenv("NTFY_TOKEN", "").strip(),
        "webhook_url": os.getenv("ALERT_WEBHOOK_URL", "").strip(),
        "idioma": normalizar(os.getenv("ALERT_LANGUAGE", "en").strip().lower()),
    }


def canais_configurados(smtp_cfg=None, canais=None):
    c = canais or canais_do_ambiente()
    return {
        "webhook": bool(c.get("webhook_url")),
        "telegram": bool(c.get("telegram_token") and c.get("telegram_chat")),
        "discord": bool(c.get("discord_url")),
        "ntfy": bool(c.get("ntfy_url")),
        "email": email_service.smtp_configurado(smtp_cfg),
    }


def montar_evento(equipamento, projeto_nome, status, status_anterior, tempo_ms=None):
    return {
        "evento": "equipamento_offline" if status == "offline" else "equipamento_online",
        "equipamento_id": equipamento.id,
        "projeto_id": equipamento.projeto_id,
        "projeto": projeto_nome,
        "equipamento": equipamento.nome,
        "ip": equipamento.ip,
        "status_anterior": status_anterior,
        "status": status,
        "tempo_ms": tempo_ms,
        "horario": datetime.now(timezone.utc).isoformat(),
    }


def montar_evento_metrica(equipamento, projeto_nome, metrica, valor, limite, situacao):
    """Temperatura/CPU acima do limite (situacao="alerta") ou de volta ao normal ("normal")."""
    return {
        "evento": f"{metrica}_{'alta' if situacao == 'alerta' else 'normal'}", "metrica": metrica,
        "equipamento_id": equipamento.id, "projeto_id": equipamento.projeto_id, "projeto": projeto_nome,
        "equipamento": equipamento.nome, "ip": equipamento.ip, "status": situacao,
        "valor": round(valor, 1), "limite": limite, "horario": datetime.now(timezone.utc).isoformat(),
    }


def texto_metrica(evento, idioma="pt"):
    unidade = " °C" if evento["metrica"] == "temperatura" else "%"
    if evento["metrica"] == "temperatura":
        chave = "🌡️ Temperatura alta: {valor}{u} (limite {limite}{u})" if evento["status"] == "alerta" else "🌡️ Temperatura normalizada: {valor}{u}"
    else:
        chave = "🔥 CPU alta: {valor}{u} (limite {limite}{u})" if evento["status"] == "alerta" else "✅ CPU normalizada: {valor}{u}"
    return tr(chave, idioma, valor=evento["valor"], limite=f"{evento['limite']:g}", u=unidade)


def formatar_mensagem(evento, idioma="pt"):
    if evento.get("metrica"):
        linhas = [texto_metrica(evento, idioma), f"{evento['equipamento']} ({evento['ip']})"]
        if evento.get("projeto"):
            linhas.append(f"{tr('Mapa', idioma)}: {evento['projeto']}")
        return "\n".join(linhas)
    titulo = tr("🔴 Equipamento OFFLINE" if evento["status"] == "offline" else "🟢 Equipamento voltou ONLINE", idioma)
    linhas = [titulo, f"{evento['equipamento']} ({evento['ip']})"]
    if evento.get("projeto"):
        linhas.append(f"{tr('Mapa', idioma)}: {evento['projeto']}")
    if evento["status"] == "online" and evento.get("tempo_ms") is not None:
        linhas.append(f"{tr('Latência', idioma)}: {evento['tempo_ms']} ms")
    if evento.get("dependentes"):
        linhas.append(texto_dependentes(evento, idioma))
    return "\n".join(linhas)


def _titulo_resumo(eventos, idioma):
    quedas = sum(1 for e in eventos if e["status"] == "offline")
    metricas = sum(1 for e in eventos if e.get("metrica"))
    voltas = len(eventos) - quedas - metricas
    partes = []
    if metricas:
        partes.append(tr("{n} alerta(s) de temperatura/CPU", idioma, n=metricas))
    if quedas:
        partes.append(tr("{n} equipamento(s) offline", idioma, n=quedas))
    if voltas:
        partes.append(tr("{n} recuperado(s)", idioma, n=voltas))
    return "NetCable: " + ", ".join(partes)


# --------------------------------------------------------------------------- canais
def erro_seguro(exc, c):
    """Mensagem de erro sem tokens/URLs secretas (o token do Telegram vai na própria URL)."""
    resposta = getattr(exc, "response", None)
    if resposta is not None:
        return f"HTTP {resposta.status_code}"
    texto = str(exc)
    for campo in ("telegram_token", "discord_url", "ntfy_token", "webhook_url", "ntfy_url"):
        if c.get(campo):
            texto = texto.replace(c[campo], "***")
    return texto[:300]


def enviar_telegram(c, texto):
    r = requests.post(f"https://api.telegram.org/bot{c['telegram_token']}/sendMessage",
                      json={"chat_id": c["telegram_chat"], "text": texto[:4000]}, timeout=WEBHOOK_TIMEOUT)
    r.raise_for_status()


def enviar_discord(c, texto):
    r = requests.post(c["discord_url"], json={"username": "NetCable", "content": texto[:1990]}, timeout=WEBHOOK_TIMEOUT)
    r.raise_for_status()


def enviar_ntfy(c, titulo, texto, urgente=False):
    cabecalhos = {"Title": titulo.encode("utf-8"), "Priority": "high" if urgente else "default",
                  "Tags": "red_circle" if urgente else "green_circle"}
    if c.get("ntfy_token"):
        cabecalhos["Authorization"] = f"Bearer {c['ntfy_token']}"
    r = requests.post(c["ntfy_url"], data=texto.encode("utf-8"), headers=cabecalhos, timeout=WEBHOOK_TIMEOUT)
    r.raise_for_status()


def enviar_webhook(c, evento):
    r = requests.post(c["webhook_url"], json=evento, timeout=WEBHOOK_TIMEOUT)
    r.raise_for_status()


def _enviar(eventos, smtp_cfg, destinatarios_por_idioma, c):
    idioma = c.get("idioma") or "en"
    texto = "\n\n".join(formatar_mensagem(e, idioma) for e in eventos)
    urgente = any(e["status"] in ("offline", "alerta") for e in eventos)
    tentativas = [
        ("webhook", c.get("webhook_url"), lambda: [enviar_webhook(c, e) for e in eventos]),
        ("Telegram", c.get("telegram_token") and c.get("telegram_chat"), lambda: enviar_telegram(c, texto)),
        ("Discord", c.get("discord_url"), lambda: enviar_discord(c, texto)),
        ("ntfy", c.get("ntfy_url"), lambda: enviar_ntfy(c, _titulo_resumo(eventos, idioma), texto, urgente)),
    ]
    for nome, ativo, funcao in tentativas:
        if not ativo:
            continue
        try:
            funcao()
        except Exception as exc:
            logger.warning("Falha ao enviar alerta %s: %s", nome, erro_seguro(exc, c))
    if destinatarios_por_idioma and email_service.smtp_configurado(smtp_cfg):
        # Um e-mail por idioma: cada usuário recebe no idioma que escolheu no NetCable.
        for idioma_email, destinatarios in destinatarios_por_idioma.items():
            try:
                assunto, texto_email, html = email_service.montar_email_alerta(eventos, idioma_email)
                email_service.enviar_email(smtp_cfg, destinatarios, assunto, texto_email, html)
            except Exception as exc:
                logger.warning("Falha ao enviar alerta por e-mail: %s", exc)


def notificar(eventos, smtp_cfg=None, destinatarios=None, canais=None):
    """Envia os eventos (lista) por todos os canais configurados, em segundo plano.
    `destinatarios`: {idioma: [e-mails]} (uma lista simples é tratada como português).
    `canais`: configuração dos canais (padrão: variáveis de ambiente)."""
    if isinstance(destinatarios, (list, tuple)):
        destinatarios = {"pt": list(destinatarios)} if destinatarios else {}
    if isinstance(eventos, dict):
        eventos = [eventos]
    if not eventos:
        return
    c = canais or canais_do_ambiente()
    ativos = canais_configurados(smtp_cfg, c)
    if not (ativos["webhook"] or ativos["telegram"] or ativos["discord"] or ativos["ntfy"] or (ativos["email"] and destinatarios)):
        return
    threading.Thread(target=_enviar, args=(eventos, smtp_cfg, destinatarios, c), name="netcable-alerta", daemon=True).start()


def testar_canal(canal, c):
    """Envia uma mensagem de teste por um canal; levanta exceção em caso de falha."""
    idioma = c.get("idioma") or "en"
    texto = tr("✅ Teste do NetCable: este canal vai receber os alertas de queda e recuperação.", idioma)
    if canal == "telegram":
        enviar_telegram(c, texto)
    elif canal == "discord":
        enviar_discord(c, texto)
    elif canal == "ntfy":
        enviar_ntfy(c, "NetCable", texto)
    elif canal == "webhook":
        enviar_webhook(c, {"evento": "teste", "mensagem": texto, "horario": datetime.now(timezone.utc).isoformat()})
    else:
        raise ValueError("Canal desconhecido.")
