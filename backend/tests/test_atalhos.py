from app import crud

BASE = {"posX": 0, "posY": 0, "width": 200, "height": 80}


def _mapa(c, nome, equipamentos):
    pid = c.post("/api/projetos", params={"nome": nome}).json()["id"]
    r = c.post(f"/api/projetos/{pid}/salvar", json={"equipamentos": equipamentos, "conexoes": []})
    assert r.status_code == 200, r.text
    return pid


def test_atalho_mostra_resumo_do_mapa_de_destino(cliente):
    c, db = cliente
    filial = _mapa(c, "Filial SP", [
        {**BASE, "id": "f-sw", "nome": "SW", "ip": "10.1.0.2", "tipo": "Switch", "status": "online"},
        {**BASE, "id": "f-ap", "nome": "AP", "ip": "10.1.0.3", "tipo": "Roteador", "status": "offline"},
        {**BASE, "id": "f-pp", "nome": "Patch", "ip": "Sem IP", "tipo": "Patch Panel", "status": "visual"},
    ])
    geral = _mapa(c, "Visão geral", [
        {**BASE, "id": "g-sp", "nome": "Filial SP", "ip": "Sem IP", "tipo": "Atalho de mapa", "status": "visual", "monitorMode": "visual", "mapaDestinoId": filial},
        {**BASE, "id": "g-eu", "nome": "Eu mesmo", "ip": "Sem IP", "tipo": "Atalho de mapa", "status": "visual", "monitorMode": "visual", "mapaDestinoId": 999999},
    ])
    dados = {e["id"]: e for e in c.get(f"/api/projetos/{geral}/dados").json()["equipamentos"]}
    assert dados["g-sp"]["mapa_destino_id"] == filial
    assert dados["g-sp"]["resumo_mapa"] == {"id": filial, "nome": "Filial SP", "online": 1, "offline": 1, "visual": 1}
    assert dados["g-eu"]["mapa_destino_id"] is None, "destino inexistente é descartado ao salvar"

    status = {e["id"]: e for e in c.get(f"/api/projetos/{geral}/status").json()["equipamentos"]}
    assert status["g-sp"]["resumo_mapa"]["offline"] == 1

    # O painel de projetos não conta atalhos como equipamentos.
    resumo = {p["nome"]: p for p in c.get("/api/projetos").json()}
    assert (resumo["Visão geral"]["online"], resumo["Visão geral"]["offline"], resumo["Visão geral"]["visual"]) == (0, 0, 0)

    # Mapa de destino excluído: o atalho avisa.
    crud.deletar_projeto(db, filial)
    status = {e["id"]: e for e in c.get(f"/api/projetos/{geral}/status").json()["equipamentos"]}
    assert status["g-sp"]["resumo_mapa"].get("removido") is True


def test_backup_zip_religa_atalhos_pelo_nome(cliente):
    c, db = cliente
    destino = _mapa(c, "Z Datacenter", [{**BASE, "id": "dc", "nome": "DC", "ip": "10.2.0.1", "tipo": "Servidor", "status": "online"}])
    _mapa(c, "A Geral", [{**BASE, "id": "a-dc", "nome": "Datacenter", "ip": "Sem IP", "tipo": "Atalho de mapa", "status": "visual",
                         "monitorMode": "visual", "mapaDestinoId": destino}])
    arquivo = c.post("/api/backup/agora").json()["arquivo"]
    zipado = c.get(f"/api/backup/arquivo/{arquivo}").content
    for p in crud.get_projetos(db):
        crud.deletar_projeto(db, p.id)
    importados = c.post("/api/projetos/importar", files={"arquivo": (arquivo, zipado, "application/zip")}).json()["importados"]
    por_nome = {i["nome"]: i["id"] for i in importados}
    geral = c.get(f"/api/projetos/{por_nome['A Geral']}/dados").json()["equipamentos"][0]
    assert geral["mapa_destino_id"] == por_nome["Z Datacenter"], "atalho aponta para o mapa importado junto"
