import time

import pytest

from app import descoberta


def test_validar_faixa():
    assert len(descoberta.validar_faixa("192.168.1.0/24")) == 254
    assert descoberta.validar_faixa("10.0.0.5-10.0.0.7") == ["10.0.0.5", "10.0.0.6", "10.0.0.7"]
    assert descoberta.validar_faixa("172.16.0.9") == ["172.16.0.9"]
    assert len(descoberta.validar_faixa("100.64.0.0/22")) == 1022  # CGNAT (ex.: Tailscale)
    for ruim, trecho in [("192.168.0.0/16", "grande demais"), ("8.8.8.0/24", "redes privadas"), ("abc", "inválida"),
                         ("10.0.0.9-10.0.0.1", "inválida"), ("fe80::/120", "inválida")]:
        with pytest.raises(ValueError, match=trecho):
            descoberta.validar_faixa(ruim)


def test_varredura_com_sondas_simuladas():
    rede = {"10.0.0.1": {53, 80, 443}, "10.0.0.7": {22, 8006}, "10.0.0.9": {445, 3389}, "10.0.0.20": {9100}}

    def tcp(ip, porta, timeout=None):
        if ip not in rede:
            return False
        return True if porta in rede[ip] else "recusada"  # host vivo responde RST

    sondas = {"tcp": tcp, "icmp": lambda ip: ip == "10.0.0.30", "rdns": lambda ip: "pve.lan" if ip == "10.0.0.7" else None}
    job = descoberta.iniciar(descoberta.validar_faixa("10.0.0.0/27"), user_id=99, sondas=sondas, em_segundo_plano=False)
    assert job["status"] == "concluido" and job["verificados"] == 30
    por_ip = {r["ip"]: r for r in job["resultados"]}
    assert list(por_ip) == ["10.0.0.1", "10.0.0.7", "10.0.0.9", "10.0.0.20", "10.0.0.30"], "ordenado numericamente"
    assert por_ip["10.0.0.1"]["tipo_sugerido"] == "Roteador"
    assert por_ip["10.0.0.7"]["tipo_sugerido"] == "Servidor" and por_ip["10.0.0.7"]["nome"] == "pve.lan"
    assert por_ip["10.0.0.9"]["tipo_sugerido"] == "PC"
    assert por_ip["10.0.0.20"]["tipo_sugerido"] == "Impressora"
    assert por_ip["10.0.0.7"]["portas"] == [22, 8006]
    assert descoberta.obter(job["id"], user_id=1) is None, "outro usuário não vê a varredura"



@pytest.mark.parametrize("ip, portas, nome, esperado", [
    ("10.0.0.5", [80, 443], "truenas.lan", "Storage/NAS"),
    ("10.0.0.5", [80, 443], "unifi-ap-sala.lan", "Access Point"),
    ("10.0.0.5", [80], "sw-core-01.lan", "Switch Gerenciável"),
    ("10.0.0.5", [80], "pfsense.home", "Firewall"),
    ("10.0.0.5", [], "HP3C2A1B.lan", "Impressora"),
    ("10.0.0.5", [80, 443], "cam01.lan", "Câmera"),
    ("10.0.0.5", [], "laptop-joao.lan", "PC"),
    ("10.0.0.5", [22, 80, 443], "Grandstream-ENGENHARIA.lan", "Outro"),  # telefone VoIP
    ("10.0.0.5", [], "M2012K11AG.lan", "Outro"),  # celular
    ("10.0.0.5", [22], "espaco-server.lan", "Servidor"),  # "esp" só casa como termo inteiro
    ("10.0.0.5", [80, 443], None, "Outro"),  # sem evidência: não chuta "Servidor"
    ("10.0.0.5", [22, 80], None, "Servidor"),
    ("10.0.0.5", [554, 80], "nas-sala", "Câmera"),  # porta forte vence o nome
])
def test_sugerir_tipo(ip, portas, nome, esperado):
    assert descoberta.sugerir_tipo(ip, portas, nome) == esperado


def test_api_descoberta(cliente, monkeypatch):
    c, db = cliente
    monkeypatch.setattr(descoberta, "sonda_tcp", lambda ip, porta, timeout=None: ip == "192.168.50.10" and porta == 80)
    monkeypatch.setattr(descoberta, "sonda_icmp", lambda ip: False)
    monkeypatch.setattr(descoberta, "nome_reverso", lambda ip: None)
    pid = c.post("/api/projetos", params={"nome": "Lab"}).json()["id"]
    c.post(f"/api/projetos/{pid}/salvar", json={"equipamentos": [{"id": "a", "nome": "Web", "ip": "192.168.50.10", "tipo": "Servidor", "status": "online",
                                                                    "posX": 0, "posY": 0, "width": 200, "height": 80}], "conexoes": []})
    assert c.post("/api/descoberta", json={"faixa": "8.8.8.8"}).status_code == 400
    r = c.post("/api/descoberta", json={"faixa": "192.168.50.0/28"})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    for _ in range(50):
        dados = c.get(f"/api/descoberta/{job_id}").json()
        if dados["status"] != "rodando":
            break
        time.sleep(0.05)
    assert dados["status"] == "concluido"
    assert [(x["ip"], x["no_mapa"]) for x in dados["resultados"]] == [("192.168.50.10", ["Lab"])]
    assert c.get("/api/descoberta/naoexiste").status_code == 404
