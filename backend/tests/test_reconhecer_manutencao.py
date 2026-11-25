from datetime import datetime, timedelta, timezone
from unittest import mock
from zoneinfo import ZoneInfo

from app import alerts, crud, email_service, models, regras_alerta


def _mapa(c, nome="Reconhecer"):
    pid = c.post("/api/projetos", params={"nome": nome}).json()["id"]
    base = {"posX": 0, "posY": 0, "width": 200, "height": 80}
    equipamentos = [
        {**base, "id": "rk-fw", "nome": "Firewall", "ip": "10.1.0.1", "tipo": "Firewall", "status": "offline"},
        {**base, "id": "rk-sw", "nome": "Switch", "ip": "10.1.0.2", "tipo": "Switch", "status": "online"},
    ]
    assert c.post(f"/api/projetos/{pid}/salvar", json={"equipamentos": equipamentos, "conexoes": []}).status_code == 200
    return pid


def _limpar(db):
    db.query(models.Reconhecimento).delete()
    db.query(models.Auditoria).delete()
    db.query(models.Configuracao).filter(models.Configuracao.chave == "alertas.lembrete_min").delete()
    db.commit()


def test_reconhecer_alerta_avisa_a_equipe_e_some_quando_volta(cliente):
    c, db = cliente
    from app import main
    pid = _mapa(c)
    try:
        assert c.post(f"/api/projetos/{pid}/equipamentos/rk-sw/reconhecer", json={}).status_code == 400  # online
        assert c.post(f"/api/projetos/{pid}/equipamentos/nao-existe/reconhecer", json={}).status_code == 404
        with mock.patch.object(main.alerts, "notificar") as notificar:
            r = c.post(f"/api/projetos/{pid}/equipamentos/rk-fw/reconhecer", json={"nota": "  indo ao rack  "})
        assert r.status_code == 200 and r.json()["usuario"] == "backup-admin" and r.json()["nota"] == "indo ao rack"
        evento = notificar.call_args[0][0][0]
        assert evento["evento"] == "equipamento_reconhecido" and evento["reconhecido_por"] == "backup-admin"
        assert "backup-admin" in alerts.formatar_mensagem(evento, "pt") and "indo ao rack" in alerts.formatar_mensagem(evento, "pt")
        assert alerts._titulo_resumo([evento], "pt") == "NetCable: 1 alerta(s) reconhecido(s)"

        status = {e["id"]: e for e in c.get(f"/api/projetos/{pid}/status").json()["equipamentos"]}
        assert status["rk-fw"]["reconhecido"]["usuario"] == "backup-admin"

        # Viewers cannot acknowledge
        v = crud.criar_usuario(db, "rk-viewer", main.pwd_context.hash("senha-forte-1"), papel="visualizador")
        try:
            h = {"Authorization": f"Bearer {main.criar_token({'sub': 'rk-viewer'})}"}
            assert c.post(f"/api/projetos/{pid}/equipamentos/rk-fw/reconhecer", json={}, headers=h).status_code == 403
        finally:
            db.delete(db.get(models.Usuario, v.id))
            db.commit()

        # Back online: the acknowledgement goes away and the recovery says who was on it
        eq = crud.get_equipamento(db, "rk-fw")
        main.registrar_monitoramento(db, eq, {"status": "offline"})  # history starts offline
        evento = main.registrar_monitoramento(db, eq, {"status": "online", "tempo_ms": 3})
        assert evento["reconhecido_por"] == "backup-admin"
        assert "Reconhecido por backup-admin" in alerts.formatar_mensagem(evento, "pt")
        assert db.get(models.Reconhecimento, "rk-fw") is None
        acoes = {a.acao for a in db.query(models.Auditoria).all()}
        assert "alerta.reconhecido" in acoes
    finally:
        _limpar(db)


def test_lembrete_de_equipamento_ainda_offline(cliente):
    c, db = cliente
    from app import main
    pid = _mapa(c, "Lembretes")
    try:
        assert c.put("/api/config/alertas", json={"lembrete_min": 2}).status_code == 400
        assert c.put("/api/config/alertas", json={"lembrete_min": 30}).json()["lembrete_min"] == 30
        main._offline_desde.clear()
        assert main.lembretes_offline(db, agora=1000.0) == []          # first seen now
        assert main.lembretes_offline(db, agora=1000.0 + 29 * 60) == []
        eventos = main.lembretes_offline(db, agora=1000.0 + 30 * 60)
        assert [e["equipamento"] for e in eventos] == ["Firewall"] and eventos[0]["lembrete"]
        texto = alerts.formatar_mensagem(eventos[0], "pt")
        assert "ainda OFFLINE" in texto and "30 min" in texto
        assert main.lembretes_offline(db, agora=1000.0 + 31 * 60) == []  # next one only after another 30 min
        # Acknowledged: no more reminders
        c.post(f"/api/projetos/{pid}/equipamentos/rk-fw/reconhecer", json={})
        assert main.lembretes_offline(db, agora=1000.0 + 120 * 60) == []
        # In maintenance: the reminder is dropped by the alert rules
        c.delete(f"/api/projetos/{pid}/equipamentos/rk-fw/reconhecer")
        c.post(f"/api/projetos/{pid}/manutencao", json={"horas": 1})
        eventos = main.lembretes_offline(db, agora=main._offline_desde["rk-fw"]["aviso"] + 30 * 60)
        assert eventos and regras_alerta.aplicar(db, eventos) == []
    finally:
        main._offline_desde.clear()
        _limpar(db)


def test_email_de_lembrete_e_reconhecimento():
    eq = mock.Mock(id="e1", projeto_id=1, nome="NAS", ip="10.0.0.9")
    lembrete = alerts.montar_evento(eq, "Casa", "offline", "offline")
    lembrete.update(lembrete=True, offline_ha_s=2 * 3600 + 5 * 60)
    reconhecido = alerts.montar_evento_reconhecido(eq, "Casa", "ana", "trocando a fonte")
    assunto, texto, html = email_service.montar_email_alerta([lembrete, reconhecido], "pt")
    assert assunto == "[NetCable] 1 equipamento(s) offline, 1 alerta(s) reconhecido(s)"
    assert "2 h 05 min" in texto and "ana reconheceu" in texto and "trocando a fonte" in html
    assert email_service.duracao_legivel(3 * 86400, "pt") == "3 dias"


# ------------------------------------------------------------------ scheduled / weekly maintenance
SP = ZoneInfo("America/Sao_Paulo")


def _utc(ano, mes, dia, h, m=0, fuso=SP):
    return datetime(ano, mes, dia, h, m, tzinfo=fuso).astimezone(timezone.utc).replace(tzinfo=None)


def test_janela_semanal_calcula_ocorrencias():
    rec = {"dias": [6], "hora": "23:00", "minutos": 180}  # Sunday 23:00 -> Monday 02:00 (São Paulo)
    # 2026-11-29 is a Sunday
    assert regras_alerta.ocorrencia_atual(rec, _utc(2026, 11, 29, 22, 59), SP) is None
    assert regras_alerta.ocorrencia_atual(rec, _utc(2026, 11, 29, 23, 0), SP) == _utc(2026, 11, 30, 2, 0)
    assert regras_alerta.ocorrencia_atual(rec, _utc(2026, 11, 30, 1, 30), SP) == _utc(2026, 11, 30, 2, 0)  # crosses midnight
    assert regras_alerta.ocorrencia_atual(rec, _utc(2026, 11, 30, 2, 0), SP) is None
    assert regras_alerta.proxima_ocorrencia(rec, _utc(2026, 11, 25, 12, 0), SP) == _utc(2026, 11, 29, 23, 0)


def test_manutencao_agendada_e_semanal_pela_api(cliente):
    c, db = cliente
    pid = _mapa(c, "Agenda")
    agora = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        # Scheduled for later: listed, but not silencing yet
        inicio = agora + timedelta(hours=2)
        r = c.post(f"/api/projetos/{pid}/manutencao", json={"inicio": inicio.isoformat(), "horas": 3, "motivo": "troca do nobreak"})
        assert r.status_code == 200, r.text
        agendada = r.json()
        assert not agendada["ativa"] and agendada["proxima"] and agendada["ate"]
        assert c.get(f"/api/projetos/{pid}/status").json()["manutencao_ate"] is None
        # Starting now keeps the scheduled one
        c.post(f"/api/projetos/{pid}/manutencao", json={"horas": 1})
        assert c.get(f"/api/projetos/{pid}/status").json()["manutencao_ate"]
        c.delete(f"/api/projetos/{pid}/manutencao")  # ends only what is active
        assert [m["id"] for m in c.get(f"/api/projetos/{pid}/manutencao").json()] == [agendada["id"]]

        # Weekly window covering "now" on every day of the week
        hora = datetime.now(regras_alerta.fuso_do_sistema(db)) - timedelta(minutes=10)
        semanal = {"dias": list(range(7)), "hora": hora.strftime("%H:%M"), "minutos": 60}
        for errado in ({**semanal, "dias": []}, {**semanal, "hora": "25:00"}, {**semanal, "minutos": 2}):
            assert c.post(f"/api/projetos/{pid}/manutencao", json={"recorrencia": errado, "equipamento_id": "rk-sw"}).status_code == 400
        r = c.post(f"/api/projetos/{pid}/manutencao", json={"recorrencia": semanal, "equipamento_id": "rk-sw"}).json()
        assert r["ativa"] and r["recorrencia"]["minutos"] == 60 and r["ate"] is None
        sw = next(e for e in c.get(f"/api/projetos/{pid}/status").json()["equipamentos"] if e["id"] == "rk-sw")
        assert sw["manutencao_ate"]

        # "End maintenance" skips this occurrence but keeps the rule
        c.delete(f"/api/projetos/{pid}/manutencao", params={"equipamento_id": "rk-sw"})
        lista = {m["id"]: m for m in c.get(f"/api/projetos/{pid}/manutencao").json()}
        assert r["id"] in lista and not lista[r["id"]]["ativa"]
        sw = next(e for e in c.get(f"/api/projetos/{pid}/status").json()["equipamentos"] if e["id"] == "rk-sw")
        assert "manutencao_ate" not in sw

        # Remove a window
        assert c.delete(f"/api/projetos/{pid}/manutencao/{r['id']}").status_code == 200
        assert c.delete(f"/api/projetos/{pid}/manutencao/{r['id']}").status_code == 404
        acoes = {a.acao for a in db.query(models.Auditoria).all()}
        assert {"manutencao.agendada", "manutencao.removida"} <= acoes
    finally:
        _limpar(db)
