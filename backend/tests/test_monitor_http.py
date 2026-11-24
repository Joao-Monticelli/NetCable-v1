"""HTTP(S) monitor against local servers (plain HTTP and HTTPS with a self-signed certificate)."""
import datetime as dt
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app import monitor_http


class _Pagina(BaseHTTPRequestHandler):
    def do_GET(self):
        codigo = 500 if self.path.startswith("/erro") else 200
        corpo = b"<html>NetCable OK page</html>"
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args):
        pass


def _servir(contexto=None):
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Pagina)
    if contexto:
        servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


@pytest.fixture()
def http_local():
    s = _servir()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


@pytest.fixture()
def https_local(tmp_path):
    chave = ec.generate_private_key(ec.SECP256R1())
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "netcable.test")])
    agora = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(agora - dt.timedelta(days=1))
            .not_valid_after(agora + dt.timedelta(days=10, hours=12)).sign(chave, hashes.SHA256()))
    (tmp_path / "c.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (tmp_path / "k.pem").write_bytes(chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(tmp_path / "c.pem", tmp_path / "k.pem")
    s = _servir(ctx)
    yield f"https://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


def test_http_online_com_texto(http_local):
    r = monitor_http.checar("127.0.0.1", {"url": http_local + "/", "texto": "OK page"})
    assert r["status"] == "online" and r["http_status"] == 200 and r["tempo_ms"] is not None


def test_http_texto_ausente_e_status_errado(http_local):
    assert monitor_http.checar("127.0.0.1", {"url": http_local, "texto": "não existe"})["status"] == "offline"
    r = monitor_http.checar("127.0.0.1", {"url": http_local + "/erro"})
    assert r["status"] == "offline" and r["error"] == "HTTP 500"
    assert monitor_http.checar("127.0.0.1", {"url": http_local + "/erro", "status": 500})["status"] == "online"


def test_url_invalida_e_padrao_pelo_ip():
    assert monitor_http.checar("10.0.0.1", {"url": "ftp://x"})["error"].startswith("URL inválida")
    assert monitor_http.montar_url("10.0.0.1", {}) == "http://10.0.0.1/"
    assert monitor_http.montar_url("10.0.0.1", {"url": "site.local/health"}) == "http://site.local/health"


def test_https_autoassinado(https_local):
    # Verifying the chain fails (self-signed)...
    r = monitor_http.checar("127.0.0.1", {"url": https_local})
    assert r["status"] == "offline" and r["error"] == "Certificado TLS inválido."
    # ...but the certificate is still read, so the expiry alert works for internal devices.
    assert r["certificado"]["dias"] == 10 and r["certificado"]["assunto"] == "netcable.test"
    r = monitor_http.checar("127.0.0.1", {"url": https_local, "verificarTls": False})
    assert r["status"] == "online" and r["certificado"]["dias"] == 10


def test_alerta_de_certificado_uma_vez_e_ao_renovar():
    from types import SimpleNamespace
    from app import main
    eq = SimpleNamespace(id="web-cert", nome="Intranet", ip="10.0.0.5", projeto_id=1, projeto=None)
    main._limites_estado.pop(("web-cert", "certificado"), None)
    assert main.avaliar_certificado(eq, {"dias": 30}, {}) == []
    [evento] = main.avaliar_certificado(eq, {"dias": 9}, {})
    assert evento["metrica"] == "certificado" and evento["status"] == "alerta" and evento["valor"] == 9
    assert main.avaliar_certificado(eq, {"dias": 8}, {}) == []  # only once
    [renovado] = main.avaliar_certificado(eq, {"dias": 90}, {})
    assert renovado["status"] == "normal"
    assert main.avaliar_certificado(eq, {"dias": 1}, {"diasCert": 0}) == []  # 0 turns it off

    from app import alerts
    assert alerts.formatar_mensagem(evento, "en").startswith("🔒 TLS certificate expires in 9 day(s)")
    vencido = {**evento, "valor": -3}
    assert alerts.texto_metrica(vencido, "pt") == "🔓 Certificado TLS VENCIDO há 3 dia(s)"
