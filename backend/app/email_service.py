"""Envio de e-mails (alertas e relatório diário) via SMTP.

A configuração do servidor SMTP é feita pelo admin na interface e fica salva
na tabela `configuracoes` (a senha é cifrada pelo main.py antes de chegar aqui).
"""

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from html import escape

from .i18n import traduzir as tr

SEGURANCAS = ("starttls", "ssl", "nenhuma")


def smtp_configurado(cfg):
    return bool(cfg and cfg.get("host") and cfg.get("remetente"))


def enviar_email(cfg, destinatarios, assunto, texto, html=None, timeout=15):
    """Envia um e-mail. `cfg`: host, porta, seguranca, usuario, senha, remetente.
    Lança exceção em caso de falha (o chamador decide como registrar)."""
    if not smtp_configurado(cfg):
        raise RuntimeError("Servidor SMTP não configurado.")
    destinatarios = [d for d in destinatarios if d]
    if not destinatarios:
        raise RuntimeError("Nenhum destinatário com e-mail cadastrado.")

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = cfg["remetente"]
    msg["To"] = ", ".join(destinatarios)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="netcable.local")
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")

    seguranca = cfg.get("seguranca") or "starttls"
    porta = int(cfg.get("porta") or (465 if seguranca == "ssl" else 587))
    contexto = ssl.create_default_context()
    if seguranca == "ssl":
        servidor = smtplib.SMTP_SSL(cfg["host"], porta, timeout=timeout, context=contexto)
    else:
        servidor = smtplib.SMTP(cfg["host"], porta, timeout=timeout)
    try:
        if seguranca == "starttls":
            servidor.starttls(context=contexto)
        if cfg.get("usuario"):
            servidor.login(cfg["usuario"], cfg.get("senha") or "")
        servidor.send_message(msg)
    finally:
        try:
            servidor.quit()
        except Exception:
            pass


# --- Conteúdo dos e-mails ---------------------------------------------------

_ESTILO = "font-family:Segoe UI,Arial,sans-serif;color:#0f172a"
_COR = {"online": "#059669", "offline": "#dc2626", "visual": "#64748b", "reconhecido": "#2563eb"}


LIMITE_DEPENDENTES = 15  # nomes listados por mensagem; o resto vira "+N"


def texto_dependentes(evento, idioma="pt"):
    """Equipamentos atrás deste (uplink) que ficaram inalcançáveis ou voltaram junto."""
    nomes = evento.get("dependentes") or []
    if not nomes:
        return ""
    lista = ", ".join(nomes[:LIMITE_DEPENDENTES]) + (f" +{len(nomes) - LIMITE_DEPENDENTES}" if len(nomes) > LIMITE_DEPENDENTES else "")
    chave = "{n} equipamento(s) atrás dele inalcançável(is): {lista}" if evento["status"] == "offline" else "{n} equipamento(s) atrás dele voltaram junto: {lista}"
    return tr(chave, idioma, n=len(nomes), lista=lista)


def duracao_legivel(segundos, idioma="pt"):
    minutos = max(1, int(segundos // 60))
    if minutos < 60:
        return f"{minutos} min"
    horas, minutos = divmod(minutos, 60)
    if horas < 48:
        return f"{horas} h {minutos:02d} min" if minutos else f"{horas} h"
    return tr("{n} dias", idioma, n=horas // 24)


def texto_extra(e, idioma="pt"):
    """Second line of reminders, acknowledgements and recoveries of acknowledged devices."""
    if e.get("evento") == "equipamento_reconhecido":
        texto = tr("👀 {usuario} reconheceu o alerta e está cuidando", idioma, usuario=e["reconhecido_por"])
        return texto + (f": {e['nota']}" if e.get("nota") else "")
    if e.get("escalado"):
        return tr("🚨 Offline há {duracao} e ninguém da equipe reconheceu o alerta", idioma, duracao=duracao_legivel(e.get("offline_ha_s") or 0, idioma))
    if e.get("lembrete"):
        return tr("⏰ Ainda offline há {duracao} e ninguém reconheceu o alerta", idioma, duracao=duracao_legivel(e.get("offline_ha_s") or 0, idioma))
    if e.get("reconhecido_por"):
        return tr("👀 Reconhecido por {usuario}", idioma, usuario=e["reconhecido_por"])
    return ""


def partes_resumo(eventos, idioma="pt"):
    """'2 equipamento(s) offline', '1 recuperado(s)'... for subjects and notification titles."""
    reconhecidos = sum(1 for e in eventos if e.get("evento") == "equipamento_reconhecido")
    quedas = sum(1 for e in eventos if e["status"] == "offline")
    certificados = sum(1 for e in eventos if e.get("metrica") == "certificado")
    metricas = sum(1 for e in eventos if e.get("metrica")) - certificados
    voltas = len(eventos) - quedas - metricas - certificados - reconhecidos
    partes = []
    if certificados:
        partes.append(tr("{n} alerta(s) de certificado", idioma, n=certificados))
    if metricas:
        partes.append(tr("{n} alerta(s) de temperatura/CPU", idioma, n=metricas))
    if quedas:
        partes.append(tr("{n} equipamento(s) offline", idioma, n=quedas))
    if voltas:
        partes.append(tr("{n} recuperado(s)", idioma, n=voltas))
    if reconhecidos:
        partes.append(tr("{n} alerta(s) reconhecido(s)", idioma, n=reconhecidos))
    return partes


def _linha_evento(e, idioma):
    if e.get("metrica"):
        from .alerts import texto_metrica  # import tardio: alerts importa este módulo
        return f"{texto_metrica(e, idioma)}  {e['equipamento']} ({e['ip']}) — {tr('mapa', idioma)} {e.get('projeto') or '-'}"
    dep = texto_dependentes(e, idioma)
    extra = texto_extra(e, idioma)
    return _linha_evento_base(e, idioma) + (f"\n      {extra}" if extra else "") + (f"\n      ↳ {dep}" if dep else "")


def _linha_evento_base(e, idioma):
    mapa = f"{tr('mapa', idioma)} {e.get('projeto') or '-'}"
    if e["status"] == "reconhecido":
        return f"👀 {tr('RECONHECIDO', idioma)}  {e['equipamento']} ({e['ip']}) — {mapa}"
    if e["status"] == "offline":
        return f"🔴 OFFLINE  {e['equipamento']} ({e['ip']}) — {mapa}"
    lat = f" — {e['tempo_ms']} ms" if e.get("tempo_ms") is not None else ""
    return f"🟢 ONLINE   {e['equipamento']} ({e['ip']}) — {mapa}{lat}"


def _rotulo_status(e, idioma):
    if e.get("metrica"):
        from .alerts import texto_metrica
        return texto_metrica(e, idioma)
    if e["status"] == "reconhecido":
        return tr("RECONHECIDO", idioma)
    return e["status"].upper()


def montar_email_alerta(eventos, idioma="pt"):
    assunto = "[NetCable] " + ", ".join(partes_resumo(eventos, idioma))
    texto = tr("Mudanças de status detectadas pelo NetCable:", idioma) + "\n\n" + "\n".join(_linha_evento(e, idioma) for e in eventos)
    linhas_html = "".join(
        f"<tr><td style='padding:6px 10px;color:{_COR.get(e['status'], '#b45309')};font-weight:bold'>{escape(_rotulo_status(e, idioma))}</td>"
        f"<td style='padding:6px 10px'>{escape(e['equipamento'])}</td>"
        f"<td style='padding:6px 10px;color:#64748b'>{escape(e['ip'] or '')}</td>"
        f"<td style='padding:6px 10px;color:#64748b'>{escape(e.get('projeto') or '-')}</td></tr>"
        + (f"<tr><td></td><td colspan='3' style='padding:0 10px 8px;color:#475569;font-size:13px'>{escape(texto_extra(e, idioma))}</td></tr>" if texto_extra(e, idioma) else "")
        + (f"<tr><td></td><td colspan='3' style='padding:0 10px 8px;color:#b45309;font-size:13px'>↳ {escape(texto_dependentes(e, idioma))}</td></tr>" if e.get('dependentes') else "")
        for e in eventos
    )
    th = lambda texto_: f"<th style='padding:6px 10px'>{escape(tr(texto_, idioma))}</th>"
    html = (
        f"<div style='{_ESTILO}'><h2 style='margin:0 0 12px'>{escape(tr('NetCable — alerta de status', idioma))}</h2>"
        f"<table style='border-collapse:collapse;font-size:14px'><tr style='color:#64748b;text-align:left'>"
        f"{th('Status')}{th('Equipamento')}{th('IP')}{th('Mapa')}</tr>{linhas_html}</table></div>"
    )
    return assunto, texto, html


def _fmt_pct(valor, idioma):
    return tr("sem dados", idioma) if valor is None else f"{valor:.2f}%"


def montar_email_relatorio(relatorio, formatar_data, idioma="pt"):
    """`relatorio`: saída de crud.montar_relatorio. `formatar_data(datetime_utc) -> str` no fuso local."""
    periodo = tr("{inicio} até {fim}", idioma, inicio=formatar_data(relatorio['inicio']), fim=formatar_data(relatorio['fim']))
    total = sum(len(m["equipamentos"]) for m in relatorio["mapas"])
    quedas = sum(eq["quedas"] for m in relatorio["mapas"] for eq in m["equipamentos"])
    offline_agora = sum(1 for m in relatorio["mapas"] for eq in m["equipamentos"] if eq["status"] == "offline")
    assunto = tr("[NetCable] Relatório diário — {quedas} queda(s), {offline} offline agora", idioma, quedas=quedas, offline=offline_agora)

    texto = [tr("Relatório do NetCable ({periodo})", idioma, periodo=periodo),
             tr("{total} equipamento(s) monitorado(s), {quedas} queda(s), {offline} offline agora.", idioma, total=total, quedas=quedas, offline=offline_agora), ""]
    html = [f"<div style='{_ESTILO}'><h2 style='margin:0 0 4px'>{escape(tr('NetCable — relatório diário', idioma))}</h2>",
            f"<p style='margin:0 0 16px;color:#64748b'>{escape(periodo)}</p>",
            f"<p><b>{total}</b> {tr('equipamento(s) monitorado(s)', idioma)} · <b style='color:#dc2626'>{quedas}</b> {tr('queda(s)', idioma)} · "
            f"<b style='color:#dc2626'>{offline_agora}</b> {tr('offline agora', idioma)}</p>"]
    if not relatorio["mapas"]:
        texto.append(tr("Nenhum equipamento monitorado.", idioma))
        html.append(f"<p>{tr('Nenhum equipamento monitorado.', idioma)}</p>")

    th = lambda texto_: f"<th style='padding:4px 10px'>{escape(tr(texto_, idioma))}</th>"
    for mapa in relatorio["mapas"]:
        texto.append(f"== {mapa['nome']} ==")
        html.append(f"<h3 style='margin:20px 0 6px'>{escape(mapa['nome'])}</h3>"
                    "<table style='border-collapse:collapse;font-size:13px'><tr style='color:#64748b;text-align:left'>"
                    f"{th('Equipamento')}{th('Agora')}{th('Disponibilidade')}{th('Quedas')}{th('Latência média')}</tr>")
        for eq in sorted(mapa["equipamentos"], key=lambda e: (e["uptime_pct"] is None, e["uptime_pct"] or 0)):
            lat = "—" if eq["latencia_media_ms"] is None else f"{eq['latencia_media_ms']} ms"
            status = tr(eq['status'], idioma)
            texto.append(f"- {eq['nome']} ({eq['ip']}): " + tr("agora {status}, disponibilidade {pct}, {quedas} queda(s), latência {lat}", idioma,
                                                               status=status, pct=_fmt_pct(eq['uptime_pct'], idioma), quedas=eq['quedas'], lat=lat))
            html.append(
                f"<tr style='border-top:1px solid #e2e8f0'><td style='padding:4px 10px'>{escape(eq['nome'])} "
                f"<span style='color:#64748b'>({escape(eq['ip'] or '')})</span></td>"
                f"<td style='padding:4px 10px;color:{_COR.get(eq['status'], '#0f172a')}'>{escape(status)}</td>"
                f"<td style='padding:4px 10px'>{_fmt_pct(eq['uptime_pct'], idioma)}</td>"
                f"<td style='padding:4px 10px;color:{'#dc2626' if eq['quedas'] else '#64748b'}'>{eq['quedas']}</td>"
                f"<td style='padding:4px 10px;color:#64748b'>{lat}</td></tr>"
            )
        html.append("</table>")
        eventos = sorted(
            ((m["momento"], eq["nome"], m["para"]) for eq in mapa["equipamentos"] for m in eq["mudancas"]),
            key=lambda x: x[0],
        )
        if eventos:
            texto.append(f"  {tr('Eventos', idioma)}:")
            html.append(f"<p style='margin:10px 0 4px;color:#64748b'>{escape(tr('Eventos no período:', idioma))}</p><ul style='margin:0;font-size:13px'>")
            for momento, nome, para in eventos:
                texto.append(f"   {formatar_data(momento)}  {nome} -> {tr(para, idioma)}")
                html.append(f"<li>{escape(formatar_data(momento))} — {escape(nome)} → "
                            f"<b style='color:{_COR.get(para, '#0f172a')}'>{escape(tr(para, idioma))}</b></li>")
            html.append("</ul>")
        texto.append("")
    html.append("</div>")
    return assunto, "\n".join(texto), "".join(html)
