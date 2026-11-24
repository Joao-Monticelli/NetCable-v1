import os
import sqlite3

from sqlalchemy import create_engine

from app import migracoes


def _banco_antigo(caminho):
    """Simula um banco criado por uma versão antiga do NetCable (sem as colunas novas)."""
    con = sqlite3.connect(caminho)
    con.executescript("""
        CREATE TABLE usuarios (id INTEGER PRIMARY KEY, username VARCHAR, password_hash VARCHAR, email VARCHAR);
        CREATE TABLE projetos (id INTEGER PRIMARY KEY, nome VARCHAR);
        CREATE TABLE equipamentos (id VARCHAR PRIMARY KEY, projeto_id INTEGER, nome VARCHAR, ip VARCHAR, tipo VARCHAR,
            status VARCHAR, ping_time FLOAT, pos_x FLOAT, pos_y FLOAT, width FLOAT, height FLOAT);
        INSERT INTO usuarios (username, password_hash) VALUES ('velho', 'hash');
    """)
    con.commit()
    con.close()


def test_migra_banco_antigo_com_copia_de_seguranca(tmp_path):
    caminho = str(tmp_path / "netcable.db")
    _banco_antigo(caminho)
    engine = create_engine(f"sqlite:///{caminho}")
    assert migracoes.aplicar(engine, caminho) == migracoes.MIGRACOES[-1][0]

    con = sqlite3.connect(caminho)
    colunas = {c[1] for c in con.execute("PRAGMA table_info(usuarios)")}
    assert {"papel", "ativo", "idioma"} <= colunas
    assert con.execute("SELECT papel FROM usuarios").fetchone()[0] == "admin"  # quem já existia vira admin
    assert {c[1] for c in con.execute("PRAGMA table_info(equipamentos)")} >= {"rack_id", "modelo_id", "notificar"}
    con.close()
    copias = os.listdir(tmp_path / "backups")
    assert len(copias) == 1 and copias[0].startswith("pre-migracao-v")

    # Rodar de novo não reaplica nada nem cria outra cópia.
    assert migracoes.aplicar(engine, caminho) == migracoes.MIGRACOES[-1][0]
    assert len(os.listdir(tmp_path / "backups")) == 1


def test_primeiro_acesso_e_chave_secreta():
    from fastapi.testclient import TestClient
    from app import main
    from app.database import DATA_DIR

    assert os.path.exists(os.path.join(DATA_DIR, "secret.key")), "chave secreta gerada na pasta de dados"
    assert main.SECRET_KEY != main.CHAVE_DEV

    c = TestClient(main.app)
    assert c.get("/api/setup").json()["necessario"] is True
    assert c.post("/api/setup", json={"username": "x", "senha": "12345678"}).status_code == 400  # usuário curto
    assert c.post("/api/setup", json={"username": "dono", "senha": "123"}).status_code == 400      # senha curta
    r = c.post("/api/setup", json={"username": "dono", "senha": "senha-forte-1", "idioma": "pt"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = c.get("/api/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["papel"] == "admin" and me["idioma"] == "pt"
    assert c.get("/api/setup").json()["necessario"] is False
    # Depois de configurado, ninguém consegue "criar o primeiro admin" de novo.
    assert c.post("/api/setup", json={"username": "invasor", "senha": "senha-forte-2"}).status_code == 409


def test_recifra_segredos_da_chave_antiga():
    from app import main
    antiga = main.segredos.fernet_de(main.CHAVE_DEV)
    with main.engine.begin() as con:
        con.exec_driver_sql("INSERT INTO configuracoes (chave, valor) VALUES ('smtp.teste', ?)", (antiga.encrypt(b'{"senha":"x"}').decode(),))
    assert main._recifrar_segredos_antigos() >= 1
    with main.engine.begin() as con:
        valor = con.exec_driver_sql("SELECT valor FROM configuracoes WHERE chave='smtp.teste'").fetchone()[0]
    assert main.abrir_config(valor) == {"senha": "x"}
