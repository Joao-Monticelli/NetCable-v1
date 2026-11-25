from app.relogio import utcnow
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app import crud, models

UTC = timezone.utc


def _hist(db, eq_id, pontos):
    for momento, status in pontos:
        db.add(models.HistoricoStatus(equipamento_id=eq_id, status=status, criado_em=momento))
    db.commit()


def test_disponibilidade_diaria_divide_na_meia_noite_local(cliente):
    c, db = cliente
    sp = ZoneInfo("America/Sao_Paulo")  # UTC-3
    agora = datetime(2026, 11, 25, 15, 0)  # 12:00 in São Paulo
    _hist(db, "dd-x", [
        (datetime(2026, 11, 24, 3, 0), "online"),    # 24/11 00:00 local
        (datetime(2026, 11, 24, 15, 0), "offline"),  # 24/11 12:00 local: 12 h offline
        (datetime(2026, 11, 25, 3, 0), "online"),    # 25/11 00:00 local
    ])
    try:
        dias = crud.disponibilidade_diaria(db, "dd-x", 3, sp, agora)
        assert dias == [(date(2026, 11, 23), None), (date(2026, 11, 24), 50.0), (date(2026, 11, 25), 100.0)]
        # In UTC, 24/11 has data from 03:00: 12 h online + 9 h offline
        assert crud.disponibilidade_diaria(db, "dd-x", 3, UTC, agora)[1] == (date(2026, 11, 24), 57.14)
    finally:
        db.query(models.HistoricoStatus).filter(models.HistoricoStatus.equipamento_id == "dd-x").delete()
        db.commit()


def _mapa(c, db):
    pid = c.post("/api/projetos", params={"nome": "Clientes"}).json()["id"]
    base = {"posX": 0, "posY": 0, "width": 200, "height": 80}
    eqs = [
        {**base, "id": "st-site", "nome": "Site", "ip": "10.5.0.1", "tipo": "Servidor", "status": "online"},
        {**base, "id": "st-erp", "nome": "ERP", "ip": "10.5.0.2", "tipo": "Servidor", "status": "offline"},
        {**base, "id": "st-sw", "nome": "Switch interno", "ip": "10.5.0.3", "tipo": "Switch", "status": "online", "statusPublico": False},
        {**base, "id": "st-doc", "nome": "Documentação", "ip": "Sem IP", "tipo": "Outro", "status": "visual", "monitorMode": "visual"},
    ]
    assert c.post(f"/api/projetos/{pid}/salvar", json={"equipamentos": eqs, "conexoes": []}).status_code == 200
    agora = utcnow()
    _hist(db, "st-site", [(agora - timedelta(days=2), "online")])
    _hist(db, "st-erp", [(agora - timedelta(days=2), "online"), (agora - timedelta(hours=1), "offline")])
    return pid


def test_pagina_de_status_publica(cliente):
    c, db = cliente
    from app import main
    pid = _mapa(c, db)
    try:
        assert c.get(f"/api/projetos/{pid}/status-publico").json() == {"token": None}
        token = c.post(f"/api/projetos/{pid}/status-publico").json()["token"]
        assert c.post(f"/api/projetos/{pid}/status-publico").json()["token"] == token  # same token until regenerated
        assert c.get(f"/api/projetos/{pid}/dados").json()["equipamentos"][2]["status_publico"] is False

        publico = c.get(f"/api/public/status/{token}", headers={"Authorization": ""})
        assert publico.status_code == 200
        dados = publico.json()
        assert dados["titulo"] == "Clientes" and dados["geral"] == "parcial"
        assert [s["nome"] for s in dados["servicos"]] == ["ERP", "Site"]  # hidden and visual devices are left out
        erp = dados["servicos"][0]
        assert erp["status"] == "offline" and len(erp["dias"]) == 90 and erp["dias"][0]["pct"] is None
        assert erp["uptime"]["1d"] is not None and erp["uptime"]["1d"] < 100
        assert "10.5.0" not in publico.text and "st-erp" not in publico.text  # no IPs or internal ids

        # Maintenance shows up and changes the status of an offline device
        main._cache_status.clear()
        c.post(f"/api/projetos/{pid}/manutencao", json={"horas": 2, "equipamento_id": "st-erp", "motivo": "atualização do ERP"})
        dados = c.get(f"/api/public/status/{token}").json()
        assert dados["geral"] == "manutencao" and dados["servicos"][0]["status"] == "manutencao"
        assert dados["manutencoes"][0]["alvo"] == "ERP" and dados["manutencoes"][0]["ativa"]

        # Regenerate and revoke
        novo = c.post(f"/api/projetos/{pid}/status-publico", params={"regenerar": True}).json()["token"]
        assert novo != token and c.get(f"/api/public/status/{token}").status_code == 404
        c.delete(f"/api/projetos/{pid}/status-publico")
        assert c.get(f"/api/public/status/{novo}").status_code == 404
        acoes = [a.acao for a in db.query(models.Auditoria).all()]
        assert {"status.criado", "status.regenerado", "status.revogado"} <= set(acoes)
    finally:
        main._cache_status.clear()
        db.query(models.HistoricoStatus).filter(models.HistoricoStatus.equipamento_id.in_(["st-site", "st-erp"])).delete(synchronize_session=False)
        db.query(models.Auditoria).delete()
        db.commit()


def test_status_publico_vai_no_backup(cliente):
    c, db = cliente
    pid = _mapa(c, db)
    try:
        exportado = c.get(f"/api/projetos/{pid}/exportar").json()
        eqs = {e["nome"]: e for e in exportado["equipamentos"]}
        assert eqs["Switch interno"]["status_publico"] is False and eqs["Site"]["status_publico"] is True
    finally:
        db.query(models.HistoricoStatus).filter(models.HistoricoStatus.equipamento_id.in_(["st-site", "st-erp"])).delete(synchronize_session=False)
        db.commit()
