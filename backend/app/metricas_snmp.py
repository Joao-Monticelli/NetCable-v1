"""Métricas via SNMP: CPU, memória, temperatura, uptime e interfaces (status e tráfego).

Tenta primeiro as MIBs padrão e depois as de fabricantes comuns:
  CPU          HOST-RESOURCES (hrProcessorLoad) · Cisco (cpmCPUTotal5minRev) · UCD (ssCpuIdle)
  Memória      HOST-RESOURCES (hrStorageRam) · UCD (memTotalReal/memAvailReal) · Cisco (ciscoMemoryPool)
  Temperatura  ENTITY-SENSOR (°C) · LM-SENSORS · MikroTik · Cisco (ciscoEnvMonTemperature)
  Interfaces   IF-MIB (ifName, ifOperStatus, ifHighSpeed, ifHC*Octets, erros)
O tráfego (bit/s) é a variação dos contadores entre duas coletas.
"""

import time

# --- OIDs
SYS_DESCR = "1.3.6.1.2.1.1.1.0"
SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
HR_PROC_LOAD = "1.3.6.1.2.1.25.3.3.1.2"
CISCO_CPU_5MIN = "1.3.6.1.4.1.9.9.109.1.1.1.1.8"
UCD_CPU_IDLE = "1.3.6.1.4.1.2021.11.11.0"
HR_STORAGE_TYPE = "1.3.6.1.2.1.25.2.3.1.2"
HR_STORAGE_UNITS = "1.3.6.1.2.1.25.2.3.1.4"
HR_STORAGE_SIZE = "1.3.6.1.2.1.25.2.3.1.5"
HR_STORAGE_USED = "1.3.6.1.2.1.25.2.3.1.6"
HR_STORAGE_RAM = "1.3.6.1.2.1.25.2.1.2"
UCD_MEM_TOTAL, UCD_MEM_AVAIL, UCD_MEM_BUFFER, UCD_MEM_CACHED = (
    "1.3.6.1.4.1.2021.4.5.0", "1.3.6.1.4.1.2021.4.6.0", "1.3.6.1.4.1.2021.4.14.0", "1.3.6.1.4.1.2021.4.15.0")
CISCO_MEM_USED, CISCO_MEM_FREE = "1.3.6.1.4.1.9.9.48.1.1.1.5", "1.3.6.1.4.1.9.9.48.1.1.1.6"
ENT_SENSOR_TYPE, ENT_SENSOR_SCALE, ENT_SENSOR_PREC, ENT_SENSOR_VALUE = (
    "1.3.6.1.2.1.99.1.1.1.1", "1.3.6.1.2.1.99.1.1.1.2", "1.3.6.1.2.1.99.1.1.1.3", "1.3.6.1.2.1.99.1.1.1.4")
LM_TEMP = "1.3.6.1.4.1.2021.13.16.2.1.3"            # mili °C
MIKROTIK_TEMP = "1.3.6.1.4.1.14988.1.1.3.10.0"       # deci °C
MIKROTIK_CPU_TEMP = "1.3.6.1.4.1.14988.1.1.3.11.0"   # deci °C
CISCO_TEMP = "1.3.6.1.4.1.9.9.13.1.3.1.3"            # °C
IF_TYPE, IF_DESCR, IF_OPER = "1.3.6.1.2.1.2.2.1.3", "1.3.6.1.2.1.2.2.1.2", "1.3.6.1.2.1.2.2.1.8"
IF_IN_ERR, IF_OUT_ERR = "1.3.6.1.2.1.2.2.1.14", "1.3.6.1.2.1.2.2.1.20"
IF_SPEED, IF_IN_OCT, IF_OUT_OCT = "1.3.6.1.2.1.2.2.1.5", "1.3.6.1.2.1.2.2.1.10", "1.3.6.1.2.1.2.2.1.16"
IF_NAME, IF_HC_IN, IF_HC_OUT = "1.3.6.1.2.1.31.1.1.1.1", "1.3.6.1.2.1.31.1.1.1.6", "1.3.6.1.2.1.31.1.1.1.10"
IF_HIGH_SPEED, IF_ALIAS = "1.3.6.1.2.1.31.1.1.1.15", "1.3.6.1.2.1.31.1.1.1.18"

# ifType de portas físicas (ethernetCsmacd, fastEther, gigabitEthernet, fibreChannel...)
TIPOS_FISICOS = {6, 62, 69, 117, 56}
CELSIUS = 8


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        try:
            return int(float(str(v).strip()))
        except (TypeError, ValueError):
            return None


def _media(valores):
    nums = [v for v in (_int(x) for x in valores) if v is not None]
    return round(sum(nums) / len(nums), 1) if nums else None


def _seguro(funcao, *args):
    """Uma MIB ausente/sem permissão não pode derrubar a coleta das outras."""
    try:
        return funcao(*args)
    except Exception:
        return {}


# --------------------------------------------------------------------------- coletores
def cpu(get, walk):
    valor = _media(_seguro(walk, HR_PROC_LOAD).values())
    if valor is None:
        valor = _media(_seguro(walk, CISCO_CPU_5MIN).values())
    if valor is None:
        idle = _int(_seguro(get, UCD_CPU_IDLE).get(UCD_CPU_IDLE))
        valor = float(100 - idle) if idle is not None else None
    return valor


def memoria(get, walk):
    tipos = _seguro(walk, HR_STORAGE_TYPE)
    ram = [i for i, tipo in tipos.items() if tipo.strip().lstrip(".") == HR_STORAGE_RAM]
    if ram:
        i = ram[0]
        v = _seguro(get, f"{HR_STORAGE_SIZE}.{i}", f"{HR_STORAGE_USED}.{i}")
        tamanho, usado = _int(v.get(f"{HR_STORAGE_SIZE}.{i}")), _int(v.get(f"{HR_STORAGE_USED}.{i}"))
        if tamanho:
            return round(100 * (usado or 0) / tamanho, 1)
    v = _seguro(get, UCD_MEM_TOTAL, UCD_MEM_AVAIL, UCD_MEM_BUFFER, UCD_MEM_CACHED)
    total = _int(v.get(UCD_MEM_TOTAL))
    if total:
        livre = sum(_int(v.get(k)) or 0 for k in (UCD_MEM_AVAIL, UCD_MEM_BUFFER, UCD_MEM_CACHED))
        return round(100 * max(0, total - livre) / total, 1)
    usado, livre = _seguro(walk, CISCO_MEM_USED), _seguro(walk, CISCO_MEM_FREE)
    if usado and livre:
        u = sum(_int(x) or 0 for x in usado.values())
        f = sum(_int(x) or 0 for x in livre.values())
        if u + f:
            return round(100 * u / (u + f), 1)
    return None


def temperatura(get, walk):
    """Maior temperatura entre os sensores (°C)."""
    leituras = []
    tipos = _seguro(walk, ENT_SENSOR_TYPE)
    celsius = [i for i, t in tipos.items() if _int(t) == CELSIUS]
    if celsius:
        valores, escalas, precisoes = _seguro(walk, ENT_SENSOR_VALUE), _seguro(walk, ENT_SENSOR_SCALE), _seguro(walk, ENT_SENSOR_PREC)
        for i in celsius:
            v = _int(valores.get(i))
            if v is None:
                continue
            expoente = ((_int(escalas.get(i)) or 9) - 9) * 3  # 9 = unidades; 8 = mili; 10 = quilo...
            leituras.append(v * (10 ** expoente) / (10 ** (_int(precisoes.get(i)) or 0)))
    if not leituras:
        leituras += [v / 1000 for v in (_int(x) for x in _seguro(walk, LM_TEMP).values()) if v is not None]
    if not leituras:
        m = _seguro(get, MIKROTIK_TEMP, MIKROTIK_CPU_TEMP)
        leituras += [v / 10 for v in (_int(x) for x in m.values()) if v is not None]
    if not leituras:
        leituras += [v for v in (_int(x) for x in _seguro(walk, CISCO_TEMP).values()) if v is not None]
    validas = [t for t in leituras if -30 <= t <= 150]
    return round(max(validas), 1) if validas else None


def interfaces(walk, anterior=None, agora=None):
    """Lista de interfaces com status e tráfego (bit/s) calculado contra a coleta anterior."""
    agora = agora or time.time()
    tipos = _seguro(walk, IF_TYPE)
    if not tipos:
        return [], {}
    nomes = _seguro(walk, IF_NAME) or _seguro(walk, IF_DESCR)
    oper = _seguro(walk, IF_OPER)
    vel_alta = _seguro(walk, IF_HIGH_SPEED)
    vel = {} if vel_alta else _seguro(walk, IF_SPEED)
    entrada = _seguro(walk, IF_HC_IN) or _seguro(walk, IF_IN_OCT)
    saida = _seguro(walk, IF_HC_OUT) or _seguro(walk, IF_OUT_OCT)
    alias = _seguro(walk, IF_ALIAS)
    erros_in, erros_out = _seguro(walk, IF_IN_ERR), _seguro(walk, IF_OUT_ERR)

    contadores = {}
    lista = []
    fisicas = sorted((i for i, t in tipos.items() if _int(t) in TIPOS_FISICOS), key=lambda i: _int(i) or 0)
    ordem = {i: n + 1 for n, i in enumerate(fisicas)}
    dt = (agora - anterior["momento"]) if anterior else None
    for i in sorted(tipos, key=lambda x: _int(x) or 0):
        e, s = _int(entrada.get(i)), _int(saida.get(i))
        contadores[i] = (e, s)
        in_bps = out_bps = None
        if anterior and dt and dt > 0 and i in anterior["contadores"]:
            e0, s0 = anterior["contadores"][i]
            if e is not None and e0 is not None and e >= e0:
                in_bps = round((e - e0) * 8 / dt)
            if s is not None and s0 is not None and s >= s0:
                out_bps = round((s - s0) * 8 / dt)
        velocidade = _int(vel_alta.get(i)) if vel_alta else ((_int(vel.get(i)) or 0) // 1_000_000 or None)
        lista.append({
            "indice": _int(i), "nome": nomes.get(i) or f"if{i}", "alias": alias.get(i) or "",
            "fisica": i in ordem, "ordem": ordem.get(i), "up": _int(oper.get(i)) == 1,
            "velocidade_mbps": velocidade or None, "in_bps": in_bps, "out_bps": out_bps,
            "erros": (_int(erros_in.get(i)) or 0) + (_int(erros_out.get(i)) or 0),
        })
    return lista, {"momento": agora, "contadores": contadores}


def coletar(get, walk, anterior=None, agora=None):
    """Coleta completa. `get(*oids) -> {oid: valor}`, `walk(oid) -> {indice: valor}`.
    Devolve (metricas, estado_para_a_proxima_coleta)."""
    # Sem _seguro: se o equipamento não responde, a coleta para aqui (evita dezenas de timeouts).
    base = get(SYS_DESCR, SYS_UPTIME)
    ticks = _int(base.get(SYS_UPTIME))
    lista, estado = interfaces(walk, anterior, agora)
    return {
        "descricao": base.get(SYS_DESCR),
        "uptime_s": ticks // 100 if ticks is not None else None,
        "cpu_pct": cpu(get, walk),
        "memoria_pct": memoria(get, walk),
        "temperatura_c": temperatura(get, walk),
        "interfaces": lista,
    }, estado
