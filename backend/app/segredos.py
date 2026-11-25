"""Secret key handling shared by the API and the key-rotation command.

The secret key signs login tokens (JWT) and encrypts stored secrets (SNMP, SMTP and
alert-channel credentials, HTTP monitor URLs) with Fernet. It comes from the SECRET_KEY
environment variable or from <data dir>/secret.key, created on first run.
"""

import base64
import hashlib
import os
import secrets

from cryptography.fernet import Fernet

CHAVE_DEV = "dev-only-change-this-secret"  # used by old versions when SECRET_KEY was not set

# (table, key column, value column) of every column that may hold encrypted values.
COLUNAS_CIFRADAS = (("equipamentos", "id", "monitor_config"), ("configuracoes", "chave", "valor"),
                    ("usuarios", "id", "totp_segredo"))


def arquivo_chave(data_dir):
    return os.path.join(data_dir, "secret.key")


def nova_chave():
    return secrets.token_urlsafe(48)


def gravar_chave(caminho, chave):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(chave)
    try:
        os.chmod(caminho, 0o600)
    except OSError:
        pass


def carregar_chave_secreta(data_dir):
    """SECRET_KEY from the environment, else the key in <data dir>/secret.key (created on first run).
    Returns (key, created_now)."""
    do_ambiente = os.getenv("SECRET_KEY", "").strip()
    if do_ambiente:
        return do_ambiente, False
    arquivo = arquivo_chave(data_dir)
    if os.path.exists(arquivo):
        with open(arquivo, encoding="utf-8") as f:
            return f.read().strip(), False
    chave = nova_chave()
    gravar_chave(arquivo, chave)
    return chave, True


def fernet_de(chave):
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(chave.encode()).digest()))
