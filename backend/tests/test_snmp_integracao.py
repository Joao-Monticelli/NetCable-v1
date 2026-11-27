"""Integração SNMPv3 de verdade contra o snmpsim (veja tests/snmpsim/gerar.py).
Só roda com NETCABLE_SNMPSIM=host:porta definido (o CI liga o simulador)."""
import os
import time

import pytest

ALVO = os.getenv("NETCABLE_SNMPSIM", "")
pytestmark = pytest.mark.skipif(not ALVO, reason="defina NETCABLE_SNMPSIM=host:porta para testar contra o snmpsim")


def _cfg(**extra):
    host, porta = ALVO.rsplit(":", 1)
    return {"host": host, "port": int(porta), "username": "netcable", "authPassword": "authpass123", "privPassword": "privpass123",
            "authProtocol": "SHA", "privProtocol": "AES", "context": "public", **extra}


def test_snmpv3_teste_e_metricas_reais():
    from app import metricas_snmp, snmp_service
    cfg = _cfg()
    for _ in range(20):  # o simulador pode demorar a subir
        try:
            assert snmp_service.test(cfg)["hostname"] == "sw-lab"
            break
        except RuntimeError:
            time.sleep(0.5)
    get = lambda *oids: snmp_service.get(cfg, *oids)
    walk = lambda oid: snmp_service.walk(cfg, oid)
    r, estado = metricas_snmp.coletar(get, walk)
    assert (r["cpu_pct"], r["memoria_pct"], r["temperatura_c"], r["uptime_s"]) == (20.0, 50.0, 47.0, 86400)
    time.sleep(2)
    r, _ = metricas_snmp.coletar(get, walk, estado)
    portas = {i["ordem"]: i for i in r["interfaces"] if i["fisica"]}
    assert set(portas) == {1, 2, 3, 4} and not portas[3]["up"] and portas[2]["erros"] == 3
    assert 8_000_000 < portas[1]["in_bps"] < 12_000_000, portas[1]  # ~10 Mbit/s simulados


def test_senha_errada_falha():
    from app import snmp_service
    with pytest.raises(RuntimeError):
        snmp_service.test(_cfg(authPassword="errada123", timeout=1))


def test_vizinhos_lldp_e_cdp_reais():
    from app import snmp_service
    vizinhos = {v["name"]: v for v in snmp_service.discover_neighbors(_cfg())}
    assert set(vizinhos) == {"firewall-qa.lab.local", "nas-qa", "printer-01", "AP-Solto(FOC1234X)"}
    fw = vizinhos["firewall-qa.lab.local"]
    assert (fw["local_port"], fw["port"], fw["address"]) == ("ge-0/0/1", "port1", "192.0.2.10")
    assert vizinhos["nas-qa"]["port"] == "eth0"  # the port id is a MAC
    ap = vizinhos["AP-Solto(FOC1234X)"]
    assert (ap["protocol"], ap["local_port"], ap["address"]) == ("CDP", "ge-0/0/3", "192.0.2.50")
