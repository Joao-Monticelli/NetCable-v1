from types import SimpleNamespace

import pytest

from app import alerts, email_service, metricas_snmp as m


def _agente(tabela):
    """get/walk falsos sobre um dicionário {oid: valor}."""
    def get(*oids):
        return {o: tabela[o] for o in oids if o in tabela}

    def walk(raiz):
        pref = raiz + "."
        return {o[len(pref):]: v for o, v in tabela.items() if o.startswith(pref)}
    return get, walk


SWITCH = {
    m.SYS_DESCR: "Lab switch", m.SYS_UPTIME: "8640000",
    f"{m.HR_PROC_LOAD}.1": "10", f"{m.HR_PROC_LOAD}.2": "30",
    f"{m.HR_STORAGE_TYPE}.1": m.HR_STORAGE_RAM, f"{m.HR_STORAGE_SIZE}.1": "1000", f"{m.HR_STORAGE_USED}.1": "250",
    f"{m.ENT_SENSOR_TYPE}.5": "8", f"{m.ENT_SENSOR_SCALE}.5": "8", f"{m.ENT_SENSOR_PREC}.5": "0", f"{m.ENT_SENSOR_VALUE}.5": "52000",  # 52000 mili°C
    f"{m.ENT_SENSOR_TYPE}.6": "10", f"{m.ENT_SENSOR_VALUE}.6": "9000",  # ventilador: ignorado
    f"{m.IF_TYPE}.1": "6", f"{m.IF_TYPE}.2": "6", f"{m.IF_TYPE}.50": "24",
    f"{m.IF_NAME}.1": "port1", f"{m.IF_NAME}.2": "port2", f"{m.IF_NAME}.50": "lo",
    f"{m.IF_OPER}.1": "1", f"{m.IF_OPER}.2": "2", f"{m.IF_OPER}.50": "1",
    f"{m.IF_HIGH_SPEED}.1": "1000", f"{m.IF_HC_IN}.1": "1000", f"{m.IF_HC_OUT}.1": "5000",
}


def test_coleta_padrao_e_taxa_de_trafego():
    get, walk = _agente(dict(SWITCH))
    r, estado = m.coletar(get, walk, agora=100.0)
    assert (r["cpu_pct"], r["memoria_pct"], r["temperatura_c"], r["uptime_s"]) == (20.0, 25.0, 52.0, 86400)
    porta1 = r["interfaces"][0]
    assert porta1["ordem"] == 1 and porta1["up"] and porta1["in_bps"] is None  # sem coleta anterior ainda
    assert [i["ordem"] for i in r["interfaces"]] == [1, 2, None], "loopback não é porta física"

    tabela = dict(SWITCH, **{f"{m.IF_HC_IN}.1": str(1000 + 125_000 * 10), f"{m.IF_HC_OUT}.1": "5000"})
    get, walk = _agente(tabela)
    r, _ = m.coletar(get, walk, anterior=estado, agora=110.0)
    assert r["interfaces"][0]["in_bps"] == 1_000_000 and r["interfaces"][0]["out_bps"] == 0


def test_contador_que_zerou_nao_vira_taxa_negativa():
    get, walk = _agente(dict(SWITCH))
    _, estado = m.coletar(get, walk, agora=1.0)
    get, walk = _agente(dict(SWITCH, **{f"{m.IF_HC_IN}.1": "10"}))  # reinício do equipamento
    r, _ = m.coletar(get, walk, anterior=estado, agora=61.0)
    assert r["interfaces"][0]["in_bps"] is None


@pytest.mark.parametrize("tabela, cpu, mem, temp", [
    # Linux/NAS com net-snmp (UCD + lm-sensors)
    ({m.SYS_UPTIME: "1", m.UCD_CPU_IDLE: "93", m.UCD_MEM_TOTAL: "1000", m.UCD_MEM_AVAIL: "300", m.UCD_MEM_BUFFER: "50",
      m.UCD_MEM_CACHED: "150", f"{m.LM_TEMP}.1": "41000", f"{m.LM_TEMP}.2": "55500"}, 7.0, 50.0, 55.5),
    # MikroTik (deci °C)
    ({m.SYS_UPTIME: "1", f"{m.HR_PROC_LOAD}.1": "4", m.MIKROTIK_TEMP: "380", m.MIKROTIK_CPU_TEMP: "455"}, 4.0, None, 45.5),
    # Cisco
    ({m.SYS_UPTIME: "1", f"{m.CISCO_CPU_5MIN}.1": "12", f"{m.CISCO_MEM_USED}.1": "300", f"{m.CISCO_MEM_FREE}.1": "700",
      f"{m.CISCO_TEMP}.1": "33", f"{m.CISCO_TEMP}.2": "999"}, 12.0, 30.0, 33.0),
])
def test_mibs_de_fabricantes(tabela, cpu, mem, temp):
    get, walk = _agente(tabela)
    r, _ = m.coletar(get, walk)
    assert (r["cpu_pct"], r["memoria_pct"], r["temperatura_c"]) == (cpu, mem, temp)


def test_equipamento_sem_resposta_interrompe_a_coleta():
    def get(*oids):
        raise RuntimeError("No SNMP response received before timeout")
    with pytest.raises(RuntimeError):
        m.coletar(get, lambda oid: {})


def test_limites_com_amostras_e_folga():
    from app import main
    eq = SimpleNamespace(id="sw-limite", projeto_id=1, nome="Core", ip="10.0.0.2")
    limites = {"temperatura": 70, "cpu": 0}
    main._limites_estado.clear()
    leituras = [72, 75, 71, 69, 66, 64]
    eventos = [main.avaliar_limites(eq, {"temperatura_c": t, "cpu_pct": 99}, limites) for t in leituras]
    assert [len(e) for e in eventos] == [0, 0, 1, 0, 0, 1], "alerta na 3ª leitura acima; normaliza só abaixo de 65"
    alta, normal = eventos[2][0], eventos[5][0]
    assert alta["evento"] == "temperatura_alta" and normal["status"] == "normal"
    assert "High temperature: 71 °C (limit 70 °C)" in alerts.formatar_mensagem(alta, "en")
    assunto, texto, html = email_service.montar_email_alerta([alta], "pt")
    assert "1 alerta(s) de temperatura/CPU" in assunto and "Temperatura alta: 71 °C" in texto


def test_api_metricas(cliente):
    from app import main
    c, db = cliente
    pid = c.post("/api/projetos", params={"nome": "SNMP"}).json()["id"]
    c.post(f"/api/projetos/{pid}/salvar", json={"equipamentos": [{"id": "snmp-sw", "nome": "SW", "ip": "10.9.9.9", "tipo": "Switch", "status": "online",
                                                                    "posX": 0, "posY": 0, "width": 200, "height": 80, "monitorMode": "snmpv3",
                                                                    "monitorConfig": {"username": "u", "context": "public"}}], "conexoes": []})
    get, walk = _agente(dict(SWITCH))
    r, _ = m.coletar(get, walk)
    main._metricas["snmp-sw"] = {**r, "coletado_em": "2026-11-17T12:00:00Z"}
    try:
        dados = c.get(f"/api/projetos/{pid}/equipamentos/snmp-sw/metricas").json()
        assert dados["snmp"] and dados["atual"]["temperatura_c"] == 52.0 and dados["limites"] == {"temperatura": 75.0, "cpu": 95.0}
        status = next(e for e in c.get(f"/api/projetos/{pid}/status").json()["equipamentos"] if e["id"] == "snmp-sw")
        assert status["snmp"]["temp"] == 52.0 and status["snmp"]["portas"][0][:2] == [1, True]
        cfg = next(e for e in c.get(f"/api/projetos/{pid}/dados").json()["equipamentos"] if e["id"] == "snmp-sw")
        assert cfg["monitor_config"]["context"] == "public" and cfg["snmp"]["cpu"] == 20.0
        assert c.put("/api/config/metricas", json={"temperatura": 200, "cpu": 90}).status_code == 400
        assert c.put("/api/config/metricas", json={"temperatura": 65, "cpu": 0}).json() == {"temperatura": 65.0, "cpu": 0.0}
    finally:
        main._metricas.pop("snmp-sw", None)
        db.query(main.models.Configuracao).filter(main.models.Configuracao.chave.like("metricas.%")).delete(synchronize_session=False)
        db.commit()
