from unittest import mock

from app import crud


def _mapa(c):
    pid = c.post("/api/projetos", params={"nome": "Escritório"}).json()["id"]
    base = {"status": "offline", "posX": 0, "posY": 0, "width": 200, "height": 80}
    equipamentos = [
        {**base, "id": "fw", "nome": "Firewall", "ip": "10.0.0.1", "tipo": "Firewall"},
        {**base, "id": "sw", "nome": "Switch", "ip": "10.0.0.2", "tipo": "Switch", "dependeDe": "fw"},
        {**base, "id": "ap", "nome": "AP", "ip": "10.0.0.3", "tipo": "Roteador", "dependeDe": "sw"},
        {**base, "id": "x", "nome": "X", "ip": "10.0.0.4", "tipo": "PC", "dependeDe": "nao-existe"},
        {**base, "id": "y", "nome": "Y", "ip": "10.0.0.5", "tipo": "PC", "dependeDe": "y"},
    ]
    assert c.post(f"/api/projetos/{pid}/salvar", json={"equipamentos": equipamentos, "conexoes": []}).status_code == 200
    return pid


def test_uplink_salvo_e_inalcancaveis_no_status(cliente):
    c, db = cliente
    pid = _mapa(c)
    dados = {e["id"]: e for e in c.get(f"/api/projetos/{pid}/dados").json()["equipamentos"]}
    assert dados["sw"]["depende_de"] == "fw" and dados["x"]["depende_de"] is None and dados["y"]["depende_de"] is None
    # Todos offline: fw é a causa de sw e ap.
    status = {e["id"]: e for e in c.get(f"/api/projetos/{pid}/status").json()["equipamentos"]}
    assert status["sw"]["inalcancavel_por"] == "fw" and status["ap"]["inalcancavel_por"] == "fw"
    assert "inalcancavel_por" not in status["fw"]


def test_janelas_de_manutencao(cliente):
    c, db = cliente
    pid = _mapa(c)
    assert c.post(f"/api/projetos/{pid}/manutencao", json={}).status_code == 400
    assert c.post(f"/api/projetos/{pid}/manutencao", json={"horas": 24 * 40}).status_code == 400
    assert c.post(f"/api/projetos/{pid}/manutencao", json={"horas": 1, "equipamento_id": "outro"}).status_code == 404
    r = c.post(f"/api/projetos/{pid}/manutencao", json={"horas": 2, "equipamento_id": "sw", "motivo": "troca de firmware"})
    assert r.status_code == 200 and r.json()["ate"].endswith("Z")
    assert c.post(f"/api/projetos/{pid}/manutencao", json={"horas": 1}).status_code == 200

    status = c.get(f"/api/projetos/{pid}/status").json()
    assert status["manutencao_ate"]
    assert next(e for e in status["equipamentos"] if e["id"] == "sw")["manutencao_ate"]
    assert len(c.get(f"/api/projetos/{pid}/manutencao").json()) == 2

    c.delete(f"/api/projetos/{pid}/manutencao")
    lista = c.get(f"/api/projetos/{pid}/manutencao").json()
    assert [m["equipamento_id"] for m in lista] == ["sw"], "encerrar a do projeto mantém a do equipamento"
    c.delete(f"/api/projetos/{pid}/manutencao", params={"equipamento_id": "sw"})
    assert c.get(f"/api/projetos/{pid}/manutencao").json() == []


def test_config_dos_canais_guarda_segredos_cifrados(cliente):
    c, db = cliente
    r = c.put("/api/config/alertas", json={"discord_url": "https://discord.com/api/webhooks/1/abc", "ntfy_url": "https://ntfy.sh/casa",
                                           "telegram_token": "123:ABC", "telegram_chat": "-100", "idioma": "pt"})
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert cfg["discord_url_definido"] and cfg["telegram_token_definido"] and cfg["ntfy_url"] == "https://ntfy.sh/casa"
    assert "123:ABC" not in r.text and "webhooks/1/abc" not in r.text
    salvo = crud.get_configuracoes(db, "alertas.")
    assert "abc" not in salvo["alertas.discord_url"], "segredo cifrado no banco"
    assert cfg["ativos"]["discord"] and cfg["ativos"]["telegram"] and not cfg["ativos"]["webhook"]

    # None mantém; "" apaga.
    r = c.put("/api/config/alertas", json={"telegram_chat": "-100"})
    assert r.json()["discord_url_definido"]
    r = c.put("/api/config/alertas", json={"discord_url": ""})
    assert not r.json()["discord_url_definido"]
    assert c.put("/api/config/alertas", json={"ntfy_url": "ntfy.sh/x"}).status_code == 400

    with mock.patch("app.alerts.requests.post") as post:
        assert c.post("/api/config/alertas/teste", json={"canal": "ntfy"}).status_code == 200
        assert post.call_args.args[0] == "https://ntfy.sh/casa"
    assert c.post("/api/config/alertas/teste", json={"canal": "discord"}).json()["detail"] == "Canal não configurado."
