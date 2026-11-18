from datetime import datetime

from app import alerts, email_service
from app.i18n import EN, idioma_do_cabecalho, traduzir


def test_idioma_do_cabecalho():
    assert idioma_do_cabecalho("pt-BR,pt;q=0.9,en;q=0.8") == "pt"
    assert idioma_do_cabecalho("pt") == "pt"
    assert idioma_do_cabecalho("en-US,en;q=0.9") == "en"
    assert idioma_do_cabecalho(None) == "en"  # inglês é o padrão


def test_traduz_mensagens_fixas_e_variaveis():
    assert traduzir("Projeto não encontrado", "en") == "Project not found"
    assert traduzir("Projeto não encontrado", "pt") == "Projeto não encontrado"
    assert traduzir("Para 2U, use de 0 a 96 portas RJ45.", "en") == "For 2U, use 0 to 96 RJ45 ports."
    assert traduzir("'FW' e 'Organizador' ocupam o mesmo U10 no rack 'Sala TI'.", "en") == "'FW' and 'Organizador' use the same U10 in rack 'Sala TI'."
    # Partes variáveis que também são mensagens conhecidas são traduzidas.
    assert traduzir("Falha no envio: Servidor SMTP não configurado.", "en") == "Sending failed: SMTP server not configured."
    # Mensagem desconhecida volta como veio.
    assert traduzir("Algo inesperado", "en") == "Algo inesperado"


def test_placeholders_iguais_nos_dois_idiomas():
    import re
    for pt, en in EN.items():
        assert set(re.findall(r"\{\w+\}", pt)) == set(re.findall(r"\{\w+\}", en)), pt


def test_email_de_alerta_em_ingles():
    eventos = [{"status": "offline", "equipamento": "Core SW", "ip": "10.0.0.1", "projeto": "Rack A"},
               {"status": "online", "equipamento": "AP", "ip": "10.0.0.2", "projeto": "Rack A", "tempo_ms": 1.5}]
    assunto, texto, html = email_service.montar_email_alerta(eventos, "en")
    assert assunto == "[NetCable] 1 device(s) offline, 1 recovered"
    assert texto.startswith("Status changes detected by NetCable:") and "— map Rack A" in texto
    assert "<th style='padding:6px 10px'>Device</th>" in html


def test_relatorio_em_ingles():
    relatorio = {"inicio": datetime(2026, 11, 16, 8), "fim": datetime(2026, 11, 17, 8), "mapas": [{
        "nome": "Rack A", "equipamentos": [{"nome": "SW", "ip": "10.0.0.1", "status": "online", "uptime_pct": 99.5,
                                             "quedas": 1, "latencia_media_ms": 2.0,
                                             "mudancas": [{"momento": datetime(2026, 11, 16, 23), "de": "online", "para": "offline"}]}]}]}
    assunto, texto, _ = email_service.montar_email_relatorio(relatorio, lambda d: d.strftime("%H:%M"), "en")
    assert assunto == "[NetCable] Daily report — 1 outage(s), 0 offline now"
    assert "now online, availability 99.50%, 1 outage(s), latency 2.0 ms" in texto
    assert "23:00  SW -> offline" in texto


def test_telegram_em_ingles():
    msg = alerts.formatar_mensagem({"status": "offline", "equipamento": "SW", "ip": "10.0.0.1", "projeto": "Rack"}, "en")
    assert msg.splitlines() == ["🔴 Device OFFLINE", "SW (10.0.0.1)", "Map: Rack"]
