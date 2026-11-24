"""Small synchronous SNMPv3 adapter used by the HTTP endpoints and the metrics collector.

PySNMP is optional at import time so old installations keep starting and can
still use the original IP/ICMP monitor until the dependency is installed.
"""

import asyncio
import threading
from collections import defaultdict


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


def discover_neighbors(config):
    """Collect the common LLDP and Cisco CDP neighbor tables via SNMP."""
    result = []
    tables = {
        "LLDP": {
            "name": "1.0.8802.1.1.2.1.4.1.1.9",
            "port": "1.0.8802.1.1.2.1.4.1.1.8",
            "platform": "1.0.8802.1.1.2.1.4.1.1.10",
        },
        "CDP": {
            "name": "1.3.6.1.4.1.9.9.23.1.2.1.1.6",
            "port": "1.3.6.1.4.1.9.9.23.1.2.1.1.7",
            "platform": "1.3.6.1.4.1.9.9.23.1.2.1.1.8",
        },
    }
    for protocol, oids in tables.items():
        rows = defaultdict(dict)
        for field, oid in oids.items():
            try:
                coluna = walk(config, oid)
            except RuntimeError as exc:
                raise RuntimeError(f"Falha ao consultar a tabela {protocol} ({field}): {exc}")
            for index, valor in coluna.items():
                rows[index][field] = valor
        for index, row in rows.items():
            if row.get("name") or row.get("port"):
                result.append({"protocol": protocol, "index": index, **row})
    return result
