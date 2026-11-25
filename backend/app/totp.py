"""Two-factor authentication: TOTP codes (RFC 6238, the 6-digit codes of Google Authenticator,
Authy, Microsoft Authenticator, 1Password...) and single-use recovery codes.

Kept dependency-free on purpose: TOTP is HMAC-SHA1 over a 30-second counter.
"""

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from urllib.parse import quote

PASSO = 30          # seconds per code
DIGITOS = 6
JANELA = 1          # accept the previous and the next code too (phone clock drift)
EMISSOR = "NetCable"
N_RECUPERACAO = 10


def novo_segredo():
    """160-bit secret, base32 (what authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def uri(segredo, usuario, emissor=EMISSOR):
    """otpauth:// link shown as a QR code."""
    rotulo = quote(f"{emissor}:{usuario}", safe=":@")
    return f"otpauth://totp/{rotulo}?secret={segredo}&issuer={quote(emissor)}&algorithm=SHA1&digits={DIGITOS}&period={PASSO}"


def _chave(segredo):
    s = segredo.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def codigo(segredo, passo):
    digest = hmac.new(_chave(segredo), struct.pack(">Q", passo), hashlib.sha1).digest()
    inicio = digest[-1] & 0x0F
    numero = struct.unpack(">I", digest[inicio:inicio + 4])[0] & 0x7FFFFFFF
    return str(numero % 10 ** DIGITOS).zfill(DIGITOS)


def passo_atual(agora=None):
    return int((time.time() if agora is None else agora) // PASSO)


def verificar(segredo, informado, ultimo_passo=None, agora=None):
    """Returns the time step of the matching code, or None.
    A code whose step is not newer than `ultimo_passo` is refused, so a code cannot be used twice."""
    informado = "".join(ch for ch in str(informado or "") if ch.isdigit())
    if len(informado) != DIGITOS or not segredo:
        return None
    atual = passo_atual(agora)
    for passo in range(atual - JANELA, atual + JANELA + 1):
        if ultimo_passo is not None and passo <= ultimo_passo:
            continue
        if hmac.compare_digest(codigo(segredo, passo), informado):
            return passo
    return None


# --------------------------------------------------------------------------- recovery codes
def _normalizar_recuperacao(texto):
    return "".join(ch for ch in str(texto or "").lower() if ch.isalnum())


def _hash(texto):
    return hashlib.sha256(_normalizar_recuperacao(texto).encode()).hexdigest()


def novos_codigos_recuperacao(n=N_RECUPERACAO):
    """(codes shown once to the user, JSON with their hashes to store)."""
    alfabeto = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i
    codigos = []
    for _ in range(n):
        bruto = "".join(secrets.choice(alfabeto) for _ in range(10))
        codigos.append(f"{bruto[:5]}-{bruto[5:]}")
    return codigos, json.dumps([_hash(c) for c in codigos])


def usar_codigo_recuperacao(guardados_json, informado):
    """(ok, JSON without the used code). Each recovery code works once."""
    try:
        hashes = json.loads(guardados_json or "[]")
    except ValueError:
        hashes = []
    if len(_normalizar_recuperacao(informado)) != 10:
        return False, guardados_json
    alvo = _hash(informado)
    for h in hashes:
        if hmac.compare_digest(h, alvo):
            hashes.remove(h)
            return True, json.dumps(hashes)
    return False, guardados_json


def restantes(guardados_json):
    try:
        return len(json.loads(guardados_json or "[]"))
    except ValueError:
        return 0
