from app.relogio import utcnow
from datetime import timedelta

from app import models


def _mapa(c, nome="Auditoria"):
    projeto = c.post(f"/api/projetos?nome={nome}").json()
    eqs = [
        {"id": "aud-sw", "nome": "Core SW", "ip": "10.9.0.1", "tipo": "Switch", "status": "online", "posX": 0, "posY": 0, "width": 200, "height": 80},
        {"id": "aud-web", "nome": "Intranet", "ip": "10.9.0.2", "tipo": "Servidor", "status": "offline", "posX": 0, "posY": 0, "width": 200, "height": 80,
         "monitorMode": "http", "monitorConfig": {"url": "https://intranet.local/health", "diasCert": 20}},
    ]
    assert c.post(f"/api/projetos/{projeto['id']}/salvar", json={"equipamentos": eqs, "conexoes": []}).status_code == 200
    return projeto["id"]


def test_auditoria_registra_acoes_e_login(cliente):
    c, db = cliente
    pid = _mapa(c)
    c.post(f"/api/projetos/{pid}/compartilhar")
    c.delete(f"/api/projetos/{pid}/compartilhar")
    r = c.post("/api/login", data={"username": "backup-admin", "password": "errada"})
    assert r.status_code == 400
    c.post("/api/login", data={"username": "backup-admin", "password": "senha-forte-1"})

    itens = c.get("/api/auditoria?limite=50").json()
    acoes = [i["acao"] for i in itens]
    for esperada in ("mapa.criado", "mapa.salvo", "link.criado", "link.revogado", "login.falhou", "login.ok"):
        assert esperada in acoes, esperada
    salvo = next(i for i in itens if i["acao"] == "mapa.salvo")
    assert salvo["usuario"] == "backup-admin" and salvo["projeto_id"] == pid and "2 device(s)" in salvo["detalhe"]
    assert all("senha" not in (i["detalhe"] or "") for i in itens)
    # Filters
    assert {i["acao"] for i in c.get("/api/auditoria?acao=login").json()} <= {"login.ok", "login.falhou"}
    db.query(models.Auditoria).delete()
    db.commit()


def test_auditoria_so_para_admin(cliente):
    c, db = cliente
    from app import main, crud
    u = crud.criar_usuario(db, "aud-editor", main.pwd_context.hash("senha-forte-1"), papel="editor")
    try:
        r = c.get("/api/auditoria", headers={"Authorization": f"Bearer {main.criar_token({'sub': 'aud-editor'})}"})
        assert r.status_code == 403
    finally:
        db.delete(db.get(models.Usuario, u.id))
        db.commit()


def test_auditoria_limpeza(cliente):
    c, db = cliente
    from app import auditoria
    db.add(models.Auditoria(usuario="x", acao="velho", criado_em=utcnow() - timedelta(days=400)))
    db.add(models.Auditoria(usuario="x", acao="novo"))
    db.commit()
    assert auditoria.limpar(db, 365) == 1
    assert [a.acao for a in auditoria.listar(db, usuario="x")] == ["novo"]
    db.query(models.Auditoria).delete()
    db.commit()


def test_mapa_http_valida_url(cliente):
    c, db = cliente
    pid = c.post("/api/projetos?nome=Http").json()["id"]
    eq = {"id": "h1", "nome": "Web", "ip": "10.0.0.1", "tipo": "Servidor", "status": "offline", "posX": 0, "posY": 0, "width": 200, "height": 80,
          "monitorMode": "http", "monitorConfig": {"url": "ftp://errado"}}
    r = c.post(f"/api/projetos/{pid}/salvar", json={"equipamentos": [eq], "conexoes": []})
    assert r.status_code == 400 and "URL" in r.json()["detail"]
    # The URL is stored encrypted and comes back to editors.
    eq["monitorConfig"] = {"url": "https://web.local", "texto": "ok"}
    assert c.post(f"/api/projetos/{pid}/salvar", json={"equipamentos": [eq], "conexoes": []}).status_code == 200
    salvo = db.get(models.Equipamento, "h1")
    assert "web.local" not in (salvo.monitor_config or "")
    dados = c.get(f"/api/projetos/{pid}/dados").json()
    assert dados["equipamentos"][0]["monitor_config"] == {"url": "https://web.local", "texto": "ok"}


def test_sla_csv(cliente):
    c, db = cliente
    pid = _mapa(c, "SLA")
    agora = utcnow()
    db.add_all([
        models.HistoricoStatus(equipamento_id="aud-sw", status="online", criado_em=agora - timedelta(hours=10)),
        models.HistoricoStatus(equipamento_id="aud-sw", status="offline", criado_em=agora - timedelta(hours=5)),
        models.HistoricoStatus(equipamento_id="aud-sw", status="online", criado_em=agora - timedelta(hours=4)),
    ])
    db.commit()
    r = c.get(f"/api/projetos/{pid}/sla.csv?dias=7")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="netcable-sla-SLA-7d.csv"' in r.headers["content-disposition"]
    linhas = r.content.decode("utf-8-sig").splitlines()
    assert linhas[0].startswith("map,device,ip,type,status_now,availability_pct,downtime_hms")
    sw = next(l for l in linhas if "Core SW" in l).split(",")
    assert sw[5] == "90.000" and sw[6] == "1:00:00" and sw[7] == "3600" and sw[8] == "1"
    assert c.get(f"/api/projetos/{pid}/sla.csv?dias=0").status_code == 400
    assert c.get("/api/projetos/999999/sla.csv").status_code == 404


def test_metrics_prometheus(cliente, monkeypatch):
    c, db = cliente
    from app import main
    from app.rotas import prometheus
    pid = _mapa(c, 'Prom "lab"')
    monkeypatch.setattr(prometheus, "METRICS_TOKEN", "")
    monkeypatch.setattr(prometheus, "METRICS_PUBLIC", False)
    assert c.get("/metrics").status_code == 404  # off by default

    monkeypatch.setattr(prometheus, "METRICS_TOKEN", "tok-123")
    sem = c.get("/metrics", headers={"Authorization": ""})
    assert sem.status_code == 401
    main._http["aud-web"] = {"http_status": 200, "certificado": {"dias": 42}}
    eq = db.get(models.Equipamento, "aud-sw")
    eq.status, eq.ping_time = "online", 1.5
    db.commit()
    r = c.get("/metrics", headers={"Authorization": "Bearer tok-123"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    texto = r.text
    assert "# TYPE netcable_device_up gauge" in texto
    assert 'netcable_device_up{map="Prom \\"lab\\"",device="Core SW",ip="10.9.0.1",type="Switch",mode="ip"} 1' in texto
    assert 'netcable_device_latency_ms{map="Prom \\"lab\\"",device="Core SW"' in texto
    assert 'netcable_tls_cert_expiry_days{map="Prom \\"lab\\"",device="Intranet",ip="10.9.0.2",type="Servidor",mode="http"} 42' in texto
    main._http.pop("aud-web", None)
    db.query(models.Auditoria).delete()
    db.commit()
