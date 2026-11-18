import io
import json
import os
import zipfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import main, crud, models, backup
from app.database import SessionLocal


def _mapa_com_rack(c, db):
    modelo = crud.salvar_modelo(db, {"nome": "GWN Teste", "fabricante": "Grandstream", "tipo": "Switch", "altura_u": 1, "portas_rj45": 4, "portas_sfp": 2})
    pid = c.post("/api/projetos", params={"nome": "Matriz"}).json()["id"]
    equipamentos = [
        {"id": "rack1", "nome": "Rack A", "ip": "Sem IP", "tipo": "Rack", "status": "visual", "posX": 0, "posY": 0, "width": 300, "height": 500, "monitorMode": "visual", "alturaU": 12},
        {"id": "sw1", "nome": "Core", "ip": "10.0.0.2", "tipo": "Switch", "status": "online", "posX": 10, "posY": 20, "width": 200, "height": 40, "rackId": "rack1", "rackU": 1, "alturaU": 1, "modeloId": modelo.id,
         "monitorMode": "snmpv3", "monitorConfig": {"username": "noc", "authPassword": "segredo-auth", "privPassword": "segredo-priv", "authProtocol": "SHA", "privProtocol": "AES"}},
        {"id": "srv1", "nome": "NAS", "ip": "10.0.0.3", "tipo": "Servidor", "status": "online", "posX": 400, "posY": 20, "width": 200, "height": 80},
    ]
    conexoes = [{"id": "e1", "source": "sw1", "target": "srv1", "label": "1G", "sourceHandle": "p:2", "targetHandle": None}]
    r = c.post(f"/api/projetos/{pid}/salvar", json={"equipamentos": equipamentos, "conexoes": conexoes})
    assert r.status_code == 200, r.text
    return pid


def test_exportar_e_importar_como_projeto_novo(cliente):
    c, db = cliente
    pid = _mapa_com_rack(c, db)
    arquivo = c.get(f"/api/projetos/{pid}/exportar").json()
    assert arquivo["formato"] == "netcable-mapa" and arquivo["versao"] == 2
    assert [m["nome"] for m in arquivo["modelos"]] == ["GWN Teste"]
    texto = json.dumps(arquivo)
    assert "segredo" not in texto, "senhas SNMP nunca vão para o arquivo"
    sw = next(e for e in arquivo["equipamentos"] if e["id"] == "sw1")
    assert sw["modelo"] == "GWN Teste" and sw["rack_id"] == "rack1" and sw["snmp"]["username"] == "noc"

    # Em outra instalação o modelo não existe: a importação recria o catálogo.
    crud.salvar_mapa(db, pid, [], [])
    crud.deletar_projeto(db, pid)
    crud.deletar_modelo(db, crud.get_modelo_por_nome(db, "GWN Teste").id)

    for vez in range(2):  # importar duas vezes não colide IDs
        r = c.post("/api/projetos/importar", files={"arquivo": ("mapa.json", json.dumps(arquivo).encode(), "application/json")})
        assert r.status_code == 200, r.text
        info = r.json()["importados"][0]
        assert info["equipamentos"] == 3 and info["conexoes"] == 1
        assert info["modelos_criados"] == (1 if vez == 0 else 0)
    nomes = sorted(p.nome for p in crud.get_projetos(db))
    assert nomes == ["Matriz", "Matriz (2)"]

    dados = c.get(f"/api/projetos/{info['id']}/dados").json()
    novo_sw = next(e for e in dados["equipamentos"] if e["nome"] == "Core")
    novo_rack = next(e for e in dados["equipamentos"] if e["nome"] == "Rack A")
    assert novo_sw["rack_id"] == novo_rack["id"] and novo_sw["id"] != "sw1"
    assert novo_sw["modelo_id"] == crud.get_modelo_por_nome(db, "GWN Teste").id
    assert dados["conexoes"][0]["source"] == novo_sw["id"] and dados["conexoes"][0]["source_handle"] == "p:2"


def test_importa_formato_antigo_e_rejeita_lixo(cliente):
    c, db = cliente
    antigo = {"projeto": "Filial", "equipamentos": [
        {"id": "a", "type": "custom", "position": {"x": 5, "y": 6}, "data": {"label": "Roteador", "ip": "192.168.0.1", "tipo": "Roteador"}},
        {"id": "b", "type": "custom", "position": {"x": 50, "y": 6}, "data": {"label": "PC", "ip": "Sem IP", "tipo": "Computador"}},
    ], "conexoes": [{"id": "x", "source": "a", "target": "b"}]}
    r = c.post("/api/projetos/importar", files={"arquivo": ("old.json", json.dumps(antigo).encode(), "application/json")})
    assert r.status_code == 200, r.text
    assert r.json()["importados"][0]["nome"] == "Filial"

    for lixo in (b"nao e json", b'{"x": 1}', b"PK\x03\x04quebrado"):
        r = c.post("/api/projetos/importar", files={"arquivo": ("x.json", lixo, "application/json")})
        assert r.status_code == 400
        assert r.json()["detail"] == "Arquivo de mapa inválido."
    assert len(crud.get_projetos(db)) == 1, "importação com erro não deixa projeto pela metade"


def test_backup_zip_completo_e_restauracao(cliente, tmp_path):
    c, db = cliente
    _mapa_com_rack(c, db)
    r = c.post("/api/backup/agora")
    assert r.status_code == 200, r.text
    nome = r.json()["arquivo"]
    assert r.json()["arquivos"][0]["nome"] == nome and r.json()["ultimo"]

    baixado = c.get(f"/api/backup/arquivo/{nome}")
    assert baixado.status_code == 200
    with zipfile.ZipFile(io.BytesIO(baixado.content)) as z:
        conteudo = set(z.namelist())
        assert {"netcable.db", "modelos.json", "manifesto.json"} <= conteudo
        assert any(n.startswith("mapas/") for n in conteudo)
        assert b"segredo" not in b"".join(z.read(n) for n in conteudo if n.endswith(".json"))

    assert c.get("/api/backup/arquivo/..%2Fsecret.key").status_code == 404
    assert c.get("/api/backup/arquivo/netcable.db").status_code == 404

    # O .zip inteiro pode ser importado pela tela de projetos.
    r = c.post("/api/projetos/importar", files={"arquivo": (nome, baixado.content, "application/zip")})
    assert r.status_code == 200 and r.json()["importados"][0]["nome"] == "Matriz (2)"


def test_config_backup_validacoes_e_retencao(cliente, tmp_path):
    c, db = cliente
    assert c.put("/api/backup", json={"horario": "25:00"}).status_code == 400
    assert c.put("/api/backup", json={"manter": 0}).status_code == 400
    assert c.put("/api/backup", json={"diretorio": "relativo/pasta"}).status_code == 400
    r = c.put("/api/backup", json={"ativo": True, "diretorio": str(tmp_path / "nova"), "horario": "02:30", "manter": 2})
    assert r.status_code == 200 and r.json()["diretorio"] == str(tmp_path / "nova")
    assert c.put("/api/backup", json={"horario": "x"}, headers={"Accept-Language": "en"}).json()["detail"] == "Invalid time (use HH:MM)."

    pasta = tmp_path / "nova"
    for i in range(4):
        (pasta / f"netcable-backup-2026010{i}-000000.zip").write_bytes(b"x")
    backup.limpar_antigos(str(pasta), 2)
    assert sorted(os.listdir(pasta)) == ["netcable-backup-20260102-000000.zip", "netcable-backup-20260103-000000.zip"]


def test_agendador_faz_um_backup_por_dia(cliente, tmp_path):
    c, db = cliente
    crud.salvar_configuracoes(db, {"backup.horario": "03:00", "backup.ultimo": "", "sistema.fuso": "UTC"})
    pasta = tmp_path / "bkp"
    main.verificar_backup_agendado(datetime(2026, 1, 5, 2, 0, tzinfo=timezone.utc))
    antes = len(os.listdir(pasta)) if pasta.exists() else 0
    main.verificar_backup_agendado(datetime(2026, 1, 5, 23, 0, tzinfo=timezone.utc))
    depois = len(os.listdir(pasta))
    main.verificar_backup_agendado(datetime(2026, 1, 5, 23, 30, tzinfo=timezone.utc))
    assert depois == antes + 1 and len(os.listdir(pasta)) == depois
    db.query(models.Configuracao).filter(models.Configuracao.chave == "sistema.fuso").delete()
    db.commit()
