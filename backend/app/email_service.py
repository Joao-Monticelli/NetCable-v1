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
_COR = {"online": "#059669", "offline": "#dc2626", "visual": "#64748b"}


def _linha_evento(e, idioma):
    mapa = f"{tr('mapa', idioma)} {e.get('projeto') or '-'}"
    if e["status"] == "offline":
        return f"🔴 OFFLINE  {e['equipamento']} ({e['ip']}) — {mapa}"
    lat = f" — {e['tempo_ms']} ms" if e.get("tempo_ms") is not None else ""
    return f"🟢 ONLINE   {e['equipamento']} ({e['ip']}) — {mapa}{lat}"


def montar_email_alerta(eventos, idioma="pt"):
    quedas = sum(1 for e in eventos if e["status"] == "offline")
    voltas = len(eventos) - quedas
    partes = []
    if quedas:
        partes.append(tr("{n} equipamento(s) offline", idioma, n=quedas))
    if voltas:
        partes.append(tr("{n} recuperado(s)", idioma, n=voltas))
    assunto = "[NetCable] " + ", ".join(partes)
    texto = tr("Mudanças de status detectadas pelo NetCable:", idioma) + "\n\n" + "\n".join(_linha_evento(e, idioma) for e in eventos)
    linhas_html = "".join(
        f"<tr><td style='padding:6px 10px;color:{_COR.get(e['status'], '#0f172a')};font-weight:bold'>{escape(e['status'].upper())}</td>"
        f"<td style='padding:6px 10px'>{escape(e['equipamento'])}</td>"
        f"<td style='padding:6px 10px;color:#64748b'>{escape(e['ip'] or '')}</td>"
        f"<td style='padding:6px 10px;color:#64748b'>{escape(e.get('projeto') or '-')}</td></tr>"
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
