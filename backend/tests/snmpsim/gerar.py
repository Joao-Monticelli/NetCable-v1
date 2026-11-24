"""Gera public.snmprec: um switch de laboratório para o snmpsim (teste de integração SNMP).

Usage (pysnmp 7 and snmpsim 1.x: pip install "snmpsim>=1.1,<2" pysmi):
  python tests/snmpsim/gerar.py
  snmpsim-command-responder --data-dir="$PWD/tests/snmpsim/dados" --cache-dir=/tmp/snmpsim-cache \
    --variation-modules-dir=<site-packages>/snmpsim/variation \
    --agent-udpv4-endpoint=127.0.0.1:11161 --v3-user=netcable --v3-auth-key=authpass123 \
    --v3-auth-proto=SHA --v3-priv-key=privpass123 --v3-priv-proto=AES
  NETCABLE_SNMPSIM=127.0.0.1:11161 pytest tests/test_snmp_integracao.py
"""
import os

linhas = {
    "1.3.6.1.2.1.1.1.0": "4|NetCable Lab Switch 24G, firmware 2.1",
    "1.3.6.1.2.1.1.2.0": "6|1.3.6.1.4.1.8072.3.2.10",
    "1.3.6.1.2.1.1.3.0": "67|8640000",  # 1 dia
    "1.3.6.1.2.1.1.5.0": "4|sw-lab",
    # CPU (HOST-RESOURCES): dois núcleos
    "1.3.6.1.2.1.25.3.3.1.2.196608": "2|17",
    "1.3.6.1.2.1.25.3.3.1.2.196609": "2|23",
    # Memória (hrStorage): RAM 1 GiB com 512 MiB usados + um disco
    "1.3.6.1.2.1.25.2.3.1.2.1": "6|1.3.6.1.2.1.25.2.1.2",
    "1.3.6.1.2.1.25.2.3.1.3.1": "4|Physical memory",
    "1.3.6.1.2.1.25.2.3.1.4.1": "2|1024",
    "1.3.6.1.2.1.25.2.3.1.5.1": "2|1048576",
    "1.3.6.1.2.1.25.2.3.1.6.1": "2|524288",
    "1.3.6.1.2.1.25.2.3.1.2.31": "6|1.3.6.1.2.1.25.2.1.4",
    "1.3.6.1.2.1.25.2.3.1.3.31": "4|/",
    "1.3.6.1.2.1.25.2.3.1.4.31": "2|4096",
    "1.3.6.1.2.1.25.2.3.1.5.31": "2|1000000",
    "1.3.6.1.2.1.25.2.3.1.6.31": "2|900000",
    # Temperatura (ENTITY-SENSOR-MIB): sensor 10 em °C
    "1.3.6.1.2.1.99.1.1.1.1.10": "2|8",
    "1.3.6.1.2.1.99.1.1.1.2.10": "2|9",
    "1.3.6.1.2.1.99.1.1.1.3.10": "2|0",
    "1.3.6.1.2.1.99.1.1.1.4.10": "2|47",
    # Sensor 11 é um ventilador (rpm): deve ser ignorado
    "1.3.6.1.2.1.99.1.1.1.1.11": "2|10",
    "1.3.6.1.2.1.99.1.1.1.4.11": "2|5400",
}
portas = {  # ifIndex: (nome, alias, tipo, oper, velocidade Mbps, taxa entrada B/s, taxa saída B/s)
    1: ("ge-0/0/1", "uplink firewall", 6, 1, 1000, 1250000, 250000),
    2: ("ge-0/0/2", "NAS", 6, 1, 1000, 125000, 2500000),
    3: ("ge-0/0/3", "", 6, 2, 1000, 0, 0),
    4: ("ge-0/0/4", "AP sala", 6, 1, 100, 12500, 6250),
    100: ("vlan10", "", 53, 1, 1000, 0, 0),
}
for i, (nome, alias, tipo, oper, vel, ent, sai) in portas.items():
    linhas[f"1.3.6.1.2.1.2.2.1.1.{i}"] = f"2|{i}"
    linhas[f"1.3.6.1.2.1.2.2.1.2.{i}"] = f"4|{nome}"
    linhas[f"1.3.6.1.2.1.2.2.1.3.{i}"] = f"2|{tipo}"
    linhas[f"1.3.6.1.2.1.2.2.1.8.{i}"] = f"2|{oper}"
    linhas[f"1.3.6.1.2.1.2.2.1.14.{i}"] = f"65|{3 if i == 2 else 0}"
    linhas[f"1.3.6.1.2.1.2.2.1.20.{i}"] = "65|0"
    linhas[f"1.3.6.1.2.1.31.1.1.1.1.{i}"] = f"4|{nome}"
    # Contadores de 64 bits que crescem com o tempo (módulo "numeric" do snmpsim)
    linhas[f"1.3.6.1.2.1.31.1.1.1.6.{i}"] = f"70:numeric|rate={ent},initial=1000000" if ent else "70|1000000"
    linhas[f"1.3.6.1.2.1.31.1.1.1.10.{i}"] = f"70:numeric|rate={sai},initial=2000000" if sai else "70|2000000"
    linhas[f"1.3.6.1.2.1.31.1.1.1.15.{i}"] = f"66|{vel}"
    linhas[f"1.3.6.1.2.1.31.1.1.1.18.{i}"] = f"4|{alias}"

chave = lambda oid: tuple(int(x) for x in oid.split("."))
pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
os.makedirs(pasta, exist_ok=True)
with open(os.path.join(pasta, "public.snmprec"), "w", newline="\n") as f:
    for oid in sorted(linhas, key=chave):
        f.write(f"{oid}|{linhas[oid]}\n")
print(len(linhas), "registros")
