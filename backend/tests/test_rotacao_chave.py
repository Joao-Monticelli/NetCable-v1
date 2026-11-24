import json
import os
import sqlite3

from app import rotacao_chave
from app.segredos import CHAVE_DEV, fernet_de


def _banco(pasta, chave):
    db = os.path.join(pasta, "netcable.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE equipamentos (id VARCHAR PRIMARY KEY, monitor_config VARCHAR)")
    con.execute("CREATE TABLE configuracoes (chave VARCHAR PRIMARY KEY, valor VARCHAR)")
    f = fernet_de(chave)
    con.execute("INSERT INTO equipamentos VALUES ('sw', ?)", (f.encrypt(json.dumps({"authPassword": "snmp-secret"}).encode()).decode(),))
    con.execute("INSERT INTO equipamentos VALUES ('pc', NULL)")
    con.execute("INSERT INTO configuracoes VALUES ('smtp.senha', ?)", (f.encrypt(b'{"senha": "smtp-secret"}').decode(),))
    con.execute("INSERT INTO configuracoes VALUES ('smtp.host', 'mail.example.com')")
    # Left over from an old version that used the development key.
    con.execute("INSERT INTO configuracoes VALUES ('alertas.webhook_url', ?)", (fernet_de(CHAVE_DEV).encrypt(b'{"v": "https://hook"}').decode(),))
    con.commit()
    con.close()
    with open(os.path.join(pasta, "secret.key"), "w") as arq:
        arq.write(chave)
    return db


def test_rotacao_recifra_tudo_e_guarda_copias(tmp_path):
    antiga = "chave-antiga-" + "x" * 40
    db = _banco(str(tmp_path), antiga)
    r = rotacao_chave.rotacionar(str(tmp_path), antiga)
    assert r["recifrados"] == 3 and r["ilegiveis"] == 0

    nova = (tmp_path / "secret.key").read_text().strip()
    assert nova != antiga and len(nova) >= 48
    assert not (tmp_path / "secret.key.new").exists()
    assert open(r["copia_chave"]).read() == antiga
    assert os.path.exists(r["copia_banco"])

    f = fernet_de(nova)
    con = sqlite3.connect(db)
    cfg = dict(con.execute("SELECT chave, valor FROM configuracoes").fetchall())
    eq = con.execute("SELECT monitor_config FROM equipamentos WHERE id='sw'").fetchone()[0]
    con.close()
    assert json.loads(f.decrypt(eq.encode())) == {"authPassword": "snmp-secret"}
    assert json.loads(f.decrypt(cfg["smtp.senha"].encode())) == {"senha": "smtp-secret"}
    assert json.loads(f.decrypt(cfg["alertas.webhook_url"].encode())) == {"v": "https://hook"}
    assert cfg["smtp.host"] == "mail.example.com"  # plain settings are untouched


def test_rotacao_avisa_valores_ilegiveis(tmp_path):
    antiga = "chave-antiga-" + "y" * 40
    db = _banco(str(tmp_path), antiga)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO configuracoes VALUES ('smtp.outra', ?)", (fernet_de("outra-chave").encrypt(b"{}").decode(),))
    con.commit()
    con.close()
    r = rotacao_chave.rotacionar(str(tmp_path), antiga, "nova-" + "z" * 40)
    assert r["recifrados"] == 3 and r["ilegiveis"] == 1


def test_comando_exige_nova_chave_com_secret_key_no_ambiente(monkeypatch, capsys):
    monkeypatch.setenv("SECRET_KEY", "da-variavel-" + "a" * 40)
    assert rotacao_chave.main(["--sim"]) == 2
    assert "--nova-chave" in capsys.readouterr().err
