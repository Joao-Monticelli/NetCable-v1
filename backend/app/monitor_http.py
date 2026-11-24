"""HTTP(S) monitor: checks a URL (status code, response time, optional keyword) and, for HTTPS,
how many days the TLS certificate has left.

Config (stored encrypted in the device's monitor_config):
    url            full URL; when empty, http://<device IP>/ is used
    status         expected status code (e.g. 200); empty accepts any 2xx/3xx
    texto          text that must appear in the response body (optional)
    verificarTls   verify the certificate chain (default true); turn off for self-signed devices
    diasCert       alert when the certificate expires in this many days or less (default 14, 0 = off)
"""

import socket
import ssl
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests
from cryptography import x509

TIMEOUT = 8
DIAS_CERT_PADRAO = 14
MAX_CORPO = 512 * 1024  # bytes read when looking for the keyword


def montar_url(ip, config):
    url = (config or {}).get("url", "").strip()
    if not url:
        return f"http://{ip}/"
    if "://" not in url:
        url = f"http://{url}"
    return url


def validar_url(url):
    partes = urlsplit(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise ValueError("URL inválida (use http:// ou https://).")
    return partes


def _data_cert(cert, campo):
    # cryptography >= 42 has *_utc; older versions return naive UTC datetimes.
    valor = getattr(cert, f"{campo}_utc", None)
    if valor is None:
        valor = getattr(cert, campo).replace(tzinfo=timezone.utc)
    return valor


def certificado(host, porta=443, timeout=TIMEOUT, agora=None):
    """Reads the server certificate (even when it is invalid or self-signed).
    Returns {expira_em, dias, emissor, assunto}."""
    contexto = ssl.create_default_context()
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, porta), timeout=timeout) as bruto:
        with contexto.wrap_socket(bruto, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    cert = x509.load_der_x509_certificate(der)
    expira = _data_cert(cert, "not_valid_after")
    agora = agora or datetime.now(timezone.utc)
    nome = lambda n: ", ".join(a.value for a in n.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)) or n.rfc4514_string()
    return {
        "expira_em": expira.isoformat().replace("+00:00", "Z"),
        "dias": int((expira - agora).total_seconds() // 86400),
        "emissor": nome(cert.issuer)[:120],
        "assunto": nome(cert.subject)[:120],
    }


def checar(ip, config=None):
    """Result in the same shape as the other monitors: {ip, status, tempo_ms, ...}."""
    config = config or {}
    url = montar_url(ip, config)
    resultado = {"ip": ip, "status": "offline", "tempo_ms": None, "url": url}
    try:
        partes = validar_url(url)
    except ValueError as exc:
        return {**resultado, "error": str(exc)}
    verificar = config.get("verificarTls", True) is not False
    esperado = config.get("status")
    texto = (config.get("texto") or "").strip()
    inicio = time.perf_counter()
    try:
        with requests.get(url, timeout=TIMEOUT, verify=verificar, allow_redirects=True, stream=True,
                          headers={"User-Agent": "NetCable-monitor"}) as r:
            resultado["tempo_ms"] = round((time.perf_counter() - inicio) * 1000, 2)
            resultado["http_status"] = r.status_code
            ok = r.status_code == int(esperado) if esperado not in (None, "") else 200 <= r.status_code < 400
            if not ok:
                resultado["error"] = f"HTTP {r.status_code}"
            elif texto:
                corpo = r.raw.read(MAX_CORPO, decode_content=True).decode(r.encoding or "utf-8", errors="replace")
                if texto not in corpo:
                    ok = False
                    resultado["error"] = "Texto esperado não encontrado na página."
            resultado["status"] = "online" if ok else "offline"
    except requests.exceptions.SSLError:
        resultado["error"] = "Certificado TLS inválido."
    except requests.RequestException as exc:
        resultado["error"] = type(exc).__name__
    if partes.scheme == "https":
        try:
            resultado["certificado"] = certificado(partes.hostname, partes.port or 443)
        except (OSError, ValueError) as exc:
            resultado["certificado"] = {"erro": type(exc).__name__}
    return resultado
