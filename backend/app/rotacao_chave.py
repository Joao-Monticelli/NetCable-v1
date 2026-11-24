"""Rotate the secret key: python -m app.rotacao_chave

Use it when the key may have leaked (e.g. data/secret.key was committed or shared).
Stop NetCable first, run the command, then start it again:

    docker compose stop netcable
    docker compose run --rm netcable python -m app.rotacao_chave
    docker compose start netcable

What it does:
  1. Copies the database to <data dir>/backups/pre-rotacao-<date>.db and keeps the old key next
     to it (secret-<date>.key.old), so old backups can still be restored.
  2. Re-encrypts every stored secret (SNMP/SMTP passwords, alert channels, HTTP monitors) with a
     new key, in a single transaction.
  3. Writes the new key to <data dir>/secret.key.

Everybody has to log in again (sessions are signed with the key). If you use the SECRET_KEY
environment variable, pass the new value with --nova-chave and update the variable afterwards.

Rotating the key does not make leaked secrets safe again: if the database leaked too, also
change the SMTP/SNMP passwords, webhook URLs and tokens stored in NetCable.
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

from cryptography.fernet import InvalidToken

from .segredos import CHAVE_DEV, COLUNAS_CIFRADAS, arquivo_chave, fernet_de, gravar_chave, nova_chave


def recifrar(conexao, chaves_antigas, chave_nova):
    """Re-encrypt every value readable with one of `chaves_antigas` using `chave_nova`.
    Returns (re-encrypted, unreadable). Plain (unencrypted) values are left alone."""
    antigas = [fernet_de(c) for c in chaves_antigas if c]
    nova = fernet_de(chave_nova)
    total = ilegiveis = 0
    tabelas = {r[0] for r in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for tabela, col_chave, col_valor in COLUNAS_CIFRADAS:
        if tabela not in tabelas:
            continue
        linhas = conexao.execute(f"SELECT {col_chave}, {col_valor} FROM {tabela} WHERE {col_valor} IS NOT NULL").fetchall()
        for ident, valor in linhas:
            if not isinstance(valor, str) or not valor.startswith("gAAAA"):
                continue  # Fernet tokens start with gAAAA; anything else is a plain setting
            claro = None
            for f in antigas:
                try:
                    claro = f.decrypt(valor.encode())
                    break
                except (InvalidToken, ValueError):
                    continue
            if claro is None:
                ilegiveis += 1
                continue
            conexao.execute(f"UPDATE {tabela} SET {col_valor} = ? WHERE {col_chave} = ?", (nova.encrypt(claro).decode(), ident))
            total += 1
    return total, ilegiveis


def _copiar_banco(db_path, destino):
    origem = sqlite3.connect(db_path)
    try:
        copia = sqlite3.connect(destino)
        with copia:
            origem.backup(copia)
        copia.close()
    finally:
        origem.close()


def rotacionar(data_dir, chave_atual, chave_nova=None, gravar_arquivo=True, agora=None):
    """Rotate the key of the installation in `data_dir`. Returns a dict with what was done."""
    db_path = os.path.join(data_dir, "netcable.db")
    chave_nova = chave_nova or nova_chave()
    if chave_nova == chave_atual:
        raise ValueError("The new key must be different from the current one.")
    carimbo = (agora or datetime.now()).strftime("%Y%m%d-%H%M%S")
    pasta = os.path.join(data_dir, "backups")
    os.makedirs(pasta, exist_ok=True)
    copia_banco = None
    if os.path.exists(db_path):
        copia_banco = os.path.join(pasta, f"pre-rotacao-{carimbo}.db")
        _copiar_banco(db_path, copia_banco)
    copia_chave = os.path.join(pasta, f"secret-{carimbo}.key.old")
    gravar_chave(copia_chave, chave_atual)

    arquivo = arquivo_chave(data_dir)
    temporario = arquivo + ".new"
    if gravar_arquivo:
        gravar_chave(temporario, chave_nova)  # if anything below fails, the new key is not lost
    total = ilegiveis = 0
    if os.path.exists(db_path):
        conexao = sqlite3.connect(db_path)
        try:
            with conexao:  # one transaction: all or nothing
                total, ilegiveis = recifrar(conexao, [chave_atual, CHAVE_DEV], chave_nova)
        finally:
            conexao.close()
    if gravar_arquivo:
        os.replace(temporario, arquivo)
    return {"recifrados": total, "ilegiveis": ilegiveis, "copia_banco": copia_banco, "copia_chave": copia_chave,
            "arquivo_chave": arquivo if gravar_arquivo else None}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m app.rotacao_chave", description="Rotate NetCable's secret key (stop NetCable first).")
    parser.add_argument("--nova-chave", help="new key to use (default: a random one). Required when SECRET_KEY is set in the environment.")
    parser.add_argument("--sim", action="store_true", help="do not ask for confirmation")
    args = parser.parse_args(argv)

    from .database import DATA_DIR  # imported here so --help works without touching the data folder

    pela_variavel = bool(os.getenv("SECRET_KEY", "").strip())
    if pela_variavel and not args.nova_chave:
        print("SECRET_KEY is set in the environment. Run again with --nova-chave \"<new value>\" "
              "and then put the same value in SECRET_KEY before starting NetCable.", file=sys.stderr)
        return 2
    if pela_variavel:
        chave_atual = os.getenv("SECRET_KEY").strip()
    elif os.path.exists(arquivo_chave(DATA_DIR)):
        with open(arquivo_chave(DATA_DIR), encoding="utf-8") as f:
            chave_atual = f.read().strip()
    else:
        print(f"No secret key found in {DATA_DIR}: nothing to rotate.", file=sys.stderr)
        return 1
    if args.nova_chave is not None and len(args.nova_chave) < 32:
        print("The new key must have at least 32 characters.", file=sys.stderr)
        return 2

    if not args.sim:
        print(f"Data folder: {DATA_DIR}\nNetCable must be stopped. Everybody will have to log in again.")
        if input("Rotate the secret key now? [y/N] ").strip().lower() not in ("y", "yes", "s", "sim"):
            print("Cancelled.")
            return 1
    r = rotacionar(DATA_DIR, chave_atual, args.nova_chave, gravar_arquivo=not pela_variavel)
    print(f"Done: {r['recifrados']} secret(s) re-encrypted.")
    if r["ilegiveis"]:
        print(f"Warning: {r['ilegiveis']} value(s) could not be read with the current key and were left as they were "
              "(enter those passwords again in NetCable).")
    if r["copia_banco"]:
        print(f"Database copy: {r['copia_banco']}")
    print(f"Old key kept in: {r['copia_chave']} (needed only to restore backups made before today).")
    if pela_variavel:
        print("Now set SECRET_KEY to the new value and start NetCable.")
    else:
        print(f"New key written to {r['arquivo_chave']}. Start NetCable again.")
    print("If the database itself leaked, also change the SMTP/SNMP passwords, webhook URLs and tokens stored in NetCable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
