"""Small synchronous SNMPv3 adapter used by the HTTP endpoints and the metrics collector.

PySNMP is optional at import time so old installations keep starting and can
still use the original IP/ICMP monitor until the dependency is installed.
"""

import asyncio
import threading


class SNMPUnavailableError(RuntimeError):
    pass


def _hlapi():
    try:
        from pysnmp.hlapi.v3arch.asyncio import (
            SnmpEngine, UsmUserData, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity, get_cmd, bulk_walk_cmd,
            usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
            usmDESPrivProtocol, usm3DESEDEPrivProtocol, usmAesCfb128Protocol,
        )
        return locals()
    except ImportError as exc:
        raise SNMPUnavailableError(
            "SNMPv3 indisponível: instale a dependência pysnmp."
        ) from exc


AUTH_PROTOCOLS = {
    "MD5": "usmHMACMD5AuthProtocol",
    "SHA": "usmHMACSHAAuthProtocol",
}
PRIV_PROTOCOLS = {
    "DES": "usmDESPrivProtocol",
    "3DES": "usm3DESEDEPrivProtocol",
    "AES": "usmAesCfb128Protocol",
}

_local = threading.local()


def _rodar(corotina):
    """Runs an SNMP coroutine on this thread's own event loop.
    pysnmp 7 is asyncio-only and an SnmpEngine is bound to the loop it first ran on, so each worker
    thread keeps one loop (and its engines) for its whole life instead of using asyncio.run()."""
    loop = getattr(_local, "loop", None)
    if loop is None or loop.is_closed():
        loop = _local.loop = asyncio.new_event_loop()
        _local.motores = {}
    return loop.run_until_complete(corotina)


def _snmp_engine(config):
    """Motor SNMP reaproveitado por thread E por credencial.
    Reaproveitar é bem mais rápido que criar um por consulta, mas o pysnmp guarda no motor as
    chaves do usuário SNMPv3: compartilhar entre credenciais diferentes usaria a senha antiga.
    O motor também fica preso ao event loop da thread (veja _rodar)."""
    chave = tuple(config.get(k) or "" for k in ("username", "authPassword", "privPassword", "authProtocol", "privProtocol"))
    motores = _local.motores
    if chave not in motores:
        if len(motores) >= 32:  # limita a memória (muitos equipamentos com credenciais distintas)
            antigo = motores.pop(next(iter(motores)))
            try:
                antigo.close_dispatcher()
            except Exception:
                pass
        motores[chave] = _hlapi()["SnmpEngine"]()
    return motores[chave]


def _user_data(config):
    h = _hlapi()
    auth_name = config.get("authProtocol", "SHA")
    priv_name = config.get("privProtocol", "AES")
    auth_protocol = h[AUTH_PROTOCOLS[auth_name]] if config.get("authPassword") else None
    priv_protocol = h[PRIV_PROTOCOLS[priv_name]] if config.get("privPassword") else None
    return h["UsmUserData"](
        config["username"],
        config.get("authPassword") or None,
        config.get("privPassword") or None,
        authProtocol=auth_protocol,
        privProtocol=priv_protocol,
    )


async def _target(config):
    h = _hlapi()
    try:
        return await h["UdpTransportTarget"].create(
            (config["host"], int(config.get("port", 161))),
            timeout=float(config.get("timeout", 2)), retries=0,
        )
    except Exception as exc:  # DNS name that does not resolve, invalid address
        raise RuntimeError(str(exc)) from exc


def _context(config):
    # Contexto SNMPv3 (opcional): alguns equipamentos usam contextos por VRF/instância.
    return _hlapi()["ContextData"](contextName=config.get("context") or "")


def _request(config, *oids):
    h = _hlapi()

    async def consulta():
        return await h["get_cmd"](
            _snmp_engine(config), _user_data(config), await _target(config), _context(config),
            *[h["ObjectType"](h["ObjectIdentity"](oid)) for oid in oids],
        )
    error_indication, error_status, error_index, var_binds = _rodar(consulta())
    if error_indication:
        raise RuntimeError(str(error_indication))
    if error_status:
        raise RuntimeError(str(error_status.prettyPrint()))
    return [(str(name), value.prettyPrint()) for name, value in var_binds]


def get(config, *oids):
    """{oid: valor (texto)} — ausentes (noSuchObject/noSuchInstance) ficam de fora."""
    resultado = {}
    for nome, valor in _request(config, *oids):
        if valor and not valor.startswith("No Such"):
            resultado[nome] = valor
    return resultado


def walk(config, oid, limite=2000):
    """{sufixo_do_indice: valor} de uma coluna de tabela (GETBULK: 25 linhas por pacote)."""
    h = _hlapi()

    async def consulta():
        linhas = {}
        async for error_indication, error_status, error_index, var_binds in h["bulk_walk_cmd"](
            _snmp_engine(config), _user_data(config), await _target(config), _context(config), 0, 25,
            h["ObjectType"](h["ObjectIdentity"](oid)), lexicographicMode=False, maxRows=limite,
        ):
            if error_indication:
                raise RuntimeError(str(error_indication))
            if error_status:
                raise RuntimeError(str(error_status.prettyPrint()))
            for name, value in var_binds:
                nome = str(name)
                if nome.startswith(oid + "."):
                    linhas[nome[len(oid) + 1:]] = value.prettyPrint()
        return linhas
    return _rodar(consulta())


def test(config):
    values = dict(_request(config, "1.3.6.1.2.1.1.5.0"))
    return {"status": "online", "hostname": next(iter(values.values()), None)}


LLDP_REM = "1.0.8802.1.1.2.1.4.1.1"      # lldpRemTable, index timeMark.localPortNum.remIndex
LLDP_LOC_PORT = "1.0.8802.1.1.2.1.3.7.1"  # lldpLocPortTable, index localPortNum
LLDP_MAN_ADDR = "1.0.8802.1.1.2.1.4.2.1"  # lldpRemManAddrTable, index ...remIndex.addrSubtype.len.address
CDP_CACHE = "1.3.6.1.4.1.9.9.23.1.2.1.1"  # cdpCacheTable, index ifIndex.deviceIndex
IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"
IF_DESCR = "1.3.6.1.2.1.2.2.1.2"


def _parece_mac(valor):
    """LLDP port/chassis ids are often a MAC ("0x001122334455" or "00:11:22:33:44:55"): not a port name."""
    texto = (valor or "").strip().lower()
    hexa = texto[2:] if texto.startswith("0x") else texto.replace(":", "").replace("-", "")
    return len(hexa) == 12 and all(c in "0123456789abcdef" for c in hexa)


def _texto_hex(valor):
    """prettyPrint of a non-printable OCTET STRING is "0x..."; printable ones come as text."""
    if valor and valor.startswith("0x"):
        try:
            texto = bytes.fromhex(valor[2:]).decode("utf-8")
            if texto.isprintable():
                return texto
        except ValueError:
            pass
    return valor


def _ip_hex(valor):
    """CDP addresses come as 4 raw bytes ("0x0a000001")."""
    if valor and valor.startswith("0x") and len(valor) == 10:
        try:
            return ".".join(str(b) for b in bytes.fromhex(valor[2:]))
        except ValueError:
            return None
    return None


def _coluna(config, oid):
    try:
        return walk(config, oid)
    except RuntimeError as exc:
        raise RuntimeError(f"Falha ao consultar {oid}: {exc}")


def _nome_porta(*candidatos):
    for valor in candidatos:
        valor = _texto_hex((valor or "").strip())
        if valor and not _parece_mac(valor):
            return valor
    return None


def discover_neighbors(config):
    """LLDP and Cisco CDP neighbors of a device, via SNMP.
    Each item: protocol, index, name (system name), port (remote port), platform, local_port, address, chassis."""
    result = []
    if_nomes = None

    def nome_interface(if_index):
        nonlocal if_nomes
        if if_nomes is None:
            if_nomes = _coluna(config, IF_NAME) or _coluna(config, IF_DESCR)
        return if_nomes.get(str(if_index))

    # LLDP
    rem = {campo: _coluna(config, f"{LLDP_REM}.{col}") for campo, col in
           (("chassis", 5), ("port_id", 7), ("port_desc", 8), ("name", 9), ("platform", 10))}
    linhas = {}
    for campo, coluna in rem.items():
        for index, valor in coluna.items():
            linhas.setdefault(index, {})[campo] = valor
    if linhas:
        loc_id, loc_desc = _coluna(config, f"{LLDP_LOC_PORT}.3"), _coluna(config, f"{LLDP_LOC_PORT}.4")
        enderecos = {}
        for index in _coluna(config, f"{LLDP_MAN_ADDR}.3"):
            partes = index.split(".")
            # timeMark.localPort.remIndex.subtype(1 = IPv4).length(4).a.b.c.d
            if len(partes) >= 9 and partes[3] == "1" and partes[4] == "4":
                enderecos.setdefault(".".join(partes[:3]), ".".join(partes[5:9]))
        for index, linha in linhas.items():
            partes = index.split(".")
            porta_local = partes[1] if len(partes) >= 3 else None
            nome = _texto_hex(linha.get("name") or "").strip() or None
            porta = _nome_porta(linha.get("port_id"), linha.get("port_desc"))
            if not (nome or porta):
                continue
            result.append({
                "protocol": "LLDP", "index": index, "name": nome, "port": porta,
                "platform": _texto_hex(linha.get("platform") or "").strip() or None,
                "local_port": _nome_porta(loc_id.get(porta_local), loc_desc.get(porta_local)) or (nome_interface(porta_local) if porta_local else None),
                "address": enderecos.get(index), "chassis": linha.get("chassis"),
            })
    # CDP (Cisco and others that speak it)
    cdp = {campo: _coluna(config, f"{CDP_CACHE}.{col}") for campo, col in (("address", 4), ("name", 6), ("port", 7), ("platform", 8))}
    linhas = {}
    for campo, coluna in cdp.items():
        for index, valor in coluna.items():
            linhas.setdefault(index, {})[campo] = valor
    for index, linha in linhas.items():
        if not (linha.get("name") or linha.get("port")):
            continue
        if_index = index.split(".")[0]
        result.append({
            "protocol": "CDP", "index": index, "name": _texto_hex(linha.get("name") or "").strip() or None,
            "port": _texto_hex(linha.get("port") or "").strip() or None, "platform": _texto_hex(linha.get("platform") or "").strip() or None,
            "local_port": nome_interface(if_index), "address": _ip_hex(linha.get("address")), "chassis": None,
        })
    return result
