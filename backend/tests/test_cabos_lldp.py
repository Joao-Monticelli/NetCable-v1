from unittest import mock

from app import cabos_lldp, snmp_service

LLDP = "1.0.8802.1.1.2.1.4.1.1"
TABELAS = {
    # lldpRemTable (timeMark.localPort.remIndex)
    f"{LLDP}.5": {"0.1.1": "0x00aabbccdd01", "0.2.1": "0x00aabbccdd02"},
    f"{LLDP}.7": {"0.1.1": "port1", "0.2.1": "0x001132aabbcc"},
    f"{LLDP}.8": {"0.1.1": "LAN 1", "0.2.1": "eth0"},
    f"{LLDP}.9": {"0.1.1": "firewall.lab.local", "0.2.1": "nas"},
    f"{LLDP}.10": {"0.1.1": "FortiGate", "0.2.1": ""},
    # lldpLocPortTable: port 1 has a name; port 2 only a MAC (falls back to its description)
    "1.0.8802.1.1.2.1.3.7.1.3": {"1": "ge-0/0/1", "2": "0x001122334402"},
    "1.0.8802.1.1.2.1.3.7.1.4": {"1": "GigabitEthernet 0/0/1", "2": "GigabitEthernet 0/0/2"},
    # lldpRemManAddrTable: IPv4 of the neighbor on port 1
    "1.0.8802.1.1.2.1.4.2.1.3": {"0.1.1.1.4.192.0.2.10": "2"},
    # cdpCacheTable (ifIndex.deviceIndex)
    "1.3.6.1.4.1.9.9.23.1.2.1.1.4": {"3.1": "0xc0000232"},
    "1.3.6.1.4.1.9.9.23.1.2.1.1.6": {"3.1": "AP-Sala(FOC1234X)"},
    "1.3.6.1.4.1.9.9.23.1.2.1.1.7": {"3.1": "GigabitEthernet0"},
    "1.3.6.1.4.1.9.9.23.1.2.1.1.8": {"3.1": "cisco AIR-AP2802I"},
    "1.3.6.1.2.1.31.1.1.1.1": {"3": "ge-0/0/3"},
}


def test_vizinhos_lldp_e_cdp_com_portas_e_enderecos():
    with mock.patch.object(snmp_service, "walk", side_effect=lambda cfg, oid: TABELAS.get(oid, {})):
        vizinhos = snmp_service.discover_neighbors({"host": "192.0.2.1"})
    por_nome = {v["name"]: v for v in vizinhos}
    fw, nas, ap = por_nome["firewall.lab.local"], por_nome["nas"], por_nome["AP-Sala(FOC1234X)"]
    assert (fw["protocol"], fw["port"], fw["local_port"], fw["address"], fw["platform"]) == ("LLDP", "port1", "ge-0/0/1", "192.0.2.10", "FortiGate")
    assert (nas["port"], nas["local_port"], nas["address"]) == ("eth0", "GigabitEthernet 0/0/2", None)  # MAC ids skipped
    assert (ap["protocol"], ap["port"], ap["local_port"], ap["address"]) == ("CDP", "GigabitEthernet0", "ge-0/0/3", "192.0.2.50")


def test_vizinhos_sem_lldp_nem_cdp():
    with mock.patch.object(snmp_service, "walk", return_value={}):
        assert snmp_service.discover_neighbors({"host": "192.0.2.1"}) == []


def test_sugestoes_juntam_as_duas_pontas_e_listam_quem_nao_esta_no_mapa():
    equipamentos = [
        {"id": "sw", "nome": "Switch Core", "ip": "192.0.2.1"},
        {"id": "fw", "nome": "Firewall", "ip": "192.0.2.10"},
        {"id": "nas", "nome": "NAS", "ip": "Sem IP"},
        {"id": "a1", "nome": "AP", "ip": "192.0.2.21"},
        {"id": "a2", "nome": "AP", "ip": "192.0.2.22"},
    ]
    vizinhos = {
        "sw": [
            {"protocol": "LLDP", "name": "firewall.lab.local", "address": "192.0.2.10", "port": "port1", "local_port": "ge-0/0/1"},
            {"protocol": "LLDP", "name": "NAS.lab.local", "address": None, "port": "eth0", "local_port": "ge-0/0/2"},
            {"protocol": "LLDP", "name": "ap", "address": None, "port": "eth0", "local_port": "ge-0/0/5"},  # 2 "AP": ambiguous
            {"protocol": "CDP", "name": "Impressora(SN1)", "address": "192.0.2.99", "port": "1", "local_port": "ge-0/0/9"},
        ],
        "fw": [  # the firewall sees the same cable from its side, by CDP
            {"protocol": "CDP", "name": "switch-core", "address": "192.0.2.1", "port": "ge-0/0/1", "local_port": None},
            {"protocol": "LLDP", "name": "Firewall", "address": "192.0.2.10", "port": "x", "local_port": "y"},  # itself
        ],
    }
    sugestoes, fora = cabos_lldp.sugerir(equipamentos, [("nas", "sw")], vizinhos)
    pares = {frozenset((s["origem_id"], s["destino_id"])): s for s in sugestoes}
    assert set(pares) == {frozenset(("sw", "fw")), frozenset(("sw", "nas"))}
    fw = pares[frozenset(("sw", "fw"))]
    assert (fw["porta_origem"], fw["porta_destino"], fw["protocolo"], fw["ja_ligado"]) == ("ge-0/0/1", "port1", "LLDP+CDP", False)
    assert pares[frozenset(("sw", "nas"))]["ja_ligado"]
    assert sorted(f["nome"] for f in fora) == ["Impressora(SN1)", "ap"]
    assert cabos_lldp.normalizar_nome("SW-Core.empresa.local") == "swcore" == cabos_lldp.normalizar_nome("sw core")
    assert cabos_lldp.normalizar_nome("192.0.2.1") == "192021"


def test_rota_descobrir_cabos(cliente):
    c, db = cliente
    pid = c.post("/api/projetos", params={"nome": "LLDP"}).json()["id"]
    base = {"posX": 0, "posY": 0, "width": 200, "height": 80}
    snmp = {"username": "netcable", "authPassword": "authpass123", "privPassword": "privpass123", "authProtocol": "SHA", "privProtocol": "AES"}
    url = f"/api/projetos/{pid}/descobrir-cabos"
    mapa = {"equipamentos": [{**base, "id": "l-fw", "nome": "Firewall", "ip": "192.0.2.10", "tipo": "Firewall", "status": "offline"}], "conexoes": []}
    c.post(f"/api/projetos/{pid}/salvar", json=mapa)
    assert c.post(url).status_code == 400  # nothing monitored by SNMPv3
    mapa["equipamentos"] += [
        {**base, "id": "l-sw", "nome": "Switch", "ip": "192.0.2.1", "tipo": "Switch", "status": "offline", "monitorMode": "snmpv3", "monitorConfig": snmp},
        {**base, "id": "l-sw2", "nome": "Switch 2", "ip": "192.0.2.2", "tipo": "Switch", "status": "offline", "monitorMode": "snmpv3", "monitorConfig": snmp},
    ]
    c.post(f"/api/projetos/{pid}/salvar", json=mapa)

    def descobrir(config):
        if config["host"] == "192.0.2.2":
            raise RuntimeError("No SNMP response received before timeout")
        assert config["authPassword"] == "authpass123"  # decrypted saved credentials
        return [{"protocol": "LLDP", "name": "fw", "address": "192.0.2.10", "port": "port1", "local_port": "ge-0/0/1"}]

    with mock.patch.object(snmp_service, "discover_neighbors", side_effect=descobrir):
        r = c.post(url)
    assert r.status_code == 200, r.text
    dados = r.json()
    consultados = {x["id"]: x for x in dados["consultados"]}
    assert consultados["l-sw"]["vizinhos"] == 1 and "timeout" in consultados["l-sw2"]["erro"]
    assert [(s["origem_id"], s["destino_id"], s["porta_origem"]) for s in dados["sugestoes"]] == [("l-sw", "l-fw", "ge-0/0/1")]
