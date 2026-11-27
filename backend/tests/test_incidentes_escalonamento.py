from unittest import mock

from app import alerts, crud, models


def _mapa(c, nome="Incidentes"):
    pid = c.post("/api/projetos", params={"nome": nome}).json()["id"]
    base = {"posX": 0, "posY": 0, "width": 200, "height": 80}
    equipamentos = [
        {**base, "id": "in-web", "nome": "Portal", "ip": "10.2.0.1", "tipo": "Servidor", "status": "online"},
        {**base, "id": "in-db", "nome": "Banco", "ip": "10.2.0.2", "tipo": "Servidor", "status": "online", "statusPublico": False},
    ]
    assert c.post(f"/api/projetos/{pid}/salvar", json={"equipamentos": equipamentos, "conexoes": []}).status_code == 200
    for eq_id in ("in-web", "in-db"):
        crud.atualizar_status_equipamento(c.db, eq_id, "online", 2)
    c.db.commit()
    token = c.post(f"/api/projetos/{pid}/status-publico").json()["token"]
    return pid, token


def test_incidentes_na_pagina_de_status(cliente):
    c, db = cliente
    c.db = db
    from app import main
    pid, token = _mapa(c)
    try:
        assert c.get(f"/api/public/status/{token}").json()["geral"] == "operacional"
        url = f"/api/projetos/{pid}/incidentes"
        assert c.post(url, json={"titulo": "x", "mensagem": "y", "impacto": "enorme"}).status_code == 400
        assert c.post(url, json={"titulo": "  ", "mensagem": "y"}).status_code == 400
        assert c.post(url, json={"titulo": "x", "mensagem": "y", "estado": "talvez"}).status_code == 400

        r = c.post(url, json={"titulo": "Lentidão no portal", "mensagem": "Estamos investigando.", "impacto": "menor",
                              "afetados": ["in-web", "in-db", "de-outro-mapa"]})
        assert r.status_code == 200, r.text
        inc = r.json()
        assert inc["afetados_ids"] == ["in-web", "in-db"] and inc["usuario"] == "backup-admin"

        pagina = c.get(f"/api/public/status/{token}").json()  # cache cleared by the change
        assert pagina["geral"] == "incidente"
        publico = pagina["incidentes"][0]
        assert publico["titulo"] == "Lentidão no portal" and publico["estado"] == "investigando"
        assert publico["afetados"] == ["Portal"]  # "Banco" is not on the status page
        assert "usuario" not in publico and "usuario" not in publico["atualizacoes"][0]

        c.put(f"{url}/{inc['id']}", json={"impacto": "grave"})
        assert c.get(f"/api/public/status/{token}").json()["geral"] == "parcial"

        r = c.post(f"{url}/{inc['id']}/atualizacoes", json={"estado": "resolvido", "mensagem": "Link trocado."})
        assert r.json()["estado"] == "resolvido" and r.json()["resolvido_em"]
        assert [a["estado"] for a in r.json()["atualizacoes"]] == ["resolvido", "investigando"]  # newest first
        pagina = c.get(f"/api/public/status/{token}").json()
        assert pagina["geral"] == "operacional" and pagina["incidentes"][0]["estado"] == "resolvido"

        # Viewers can read the list but not post
        v = crud.criar_usuario(db, "in-viewer", main.pwd_context.hash("senha-forte-1"), papel="visualizador")
        try:
            h = {"Authorization": f"Bearer {main.criar_token({'sub': 'in-viewer'})}"}
            assert c.get(url, headers=h).status_code == 200
            assert c.post(url, json={"titulo": "x", "mensagem": "y"}, headers=h).status_code == 403
        finally:
            db.delete(db.get(models.Usuario, v.id))
            db.commit()

        assert c.delete(f"{url}/{inc['id']}").status_code == 200
        assert c.get(f"/api/public/status/{token}").json()["incidentes"] == []
        acoes = {a.acao for a in db.query(models.Auditoria).all()}
        assert {"incidente.criado", "incidente.atualizado", "incidente.excluido"} <= acoes
    finally:
        db.query(models.Auditoria).delete()
        db.commit()


def test_escalonamento_de_queda_sem_reconhecimento(cliente):
    c, db = cliente
    c.db = db
    from app import main, monitoramento as mon, regras_alerta
    pid, _ = _mapa(c, "Escalonamento")
    try:
        assert c.put("/api/config/alertas", json={"escalar_min": 3}).status_code == 400
        assert c.put("/api/config/alertas", json={"escalar_emails": "chefe@"}).status_code == 400
        assert c.put("/api/config/alertas", json={"escalar_ntfy_url": "ftp://x"}).status_code == 400
        r = c.put("/api/config/alertas", json={"escalar_min": 15, "escalar_emails": "chefe@empresa.com; noc@empresa.com chefe@empresa.com",
                                                "escalar_ntfy_url": "https://ntfy.sh/plantao"})
        dados = r.json()
        assert dados["escalar_min"] == 15 and dados["escalar_emails"] == "chefe@empresa.com, noc@empresa.com"
        assert dados["escalar_ntfy_url_definido"] and "escalar_ntfy_url" not in dados

        crud.atualizar_status_equipamento(db, "in-web", "offline", None)
        crud.atualizar_status_equipamento(db, "in-db", "offline", None)
        db.commit()
        mon._offline_desde.clear()
        assert mon.escalonamentos_offline(db, agora=1000.0) == []  # first seen now
        assert mon.escalonamentos_offline(db, agora=1000.0 + 14 * 60) == []
        regras_alerta.reconhecer(db, crud.get_equipamento(db, "in-db"), "alguem", None)
        eventos = mon.escalonamentos_offline(db, agora=1000.0 + 15 * 60)
        assert [e["equipamento"] for e in eventos] == ["Portal"]  # "Banco" was acknowledged
        assert eventos[0]["escalado"] and eventos[0]["offline_ha_s"] == 900
        assert mon.escalonamentos_offline(db, agora=1000.0 + 60 * 60) == []  # once per outage
        texto = alerts.formatar_mensagem(eventos[0], "pt")
        assert "Alerta escalado" in texto and "15 min" in texto

        with mock.patch.object(mon.alerts, "notificar") as notificar:
            mon.enviar_escalonamentos(db, eventos)
        _, smtp, destinatarios, canais = notificar.call_args[0]
        assert list(destinatarios.values()) == [["chefe@empresa.com", "noc@empresa.com"]]
        assert canais["ntfy_url"] == "https://ntfy.sh/plantao" and not canais["telegram_chat"] and not canais.get("webhook_url")

        # Back online and down again: a new outage escalates again
        main.registrar_monitoramento(db, crud.get_equipamento(db, "in-web"), {"status": "online", "tempo_ms": 1})
        main.registrar_monitoramento(db, crud.get_equipamento(db, "in-web"), {"status": "offline"})
        mon._offline_desde["in-web"] = {"desde": 0.0, "aviso": 0.0}
        assert [e["equipamento"] for e in mon.escalonamentos_offline(db, agora=2000.0)] == ["Portal"]

        assert c.put("/api/config/alertas", json={"escalar_min": 0}).json()["escalar_min"] == 0
        mon._offline_desde.clear()
        assert mon.escalonamentos_offline(db, agora=1e9) == []
    finally:
        db.query(models.Reconhecimento).delete()
        db.commit()
