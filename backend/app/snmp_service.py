"""Small synchronous SNMPv3 adapter used by the HTTP endpoints.

PySNMP is optional at import time so old installations keep starting and can
still use the original IP/ICMP monitor until the dependency is installed.
"""

from collections import defaultdict


class SNMPUnavailableError(RuntimeError):
    pass


def _hlapi():
    try:
        from pysnmp.hlapi import (
            SnmpEngine, UsmUserData, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity, getCmd, nextCmd,
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


def _target(config):
    h = _hlapi()
    return h["UdpTransportTarget"](
        (config["host"], int(config.get("port", 161))),
        timeout=float(config.get("timeout", 2)), retries=0,
    )


def _request(config, oid):
    h = _hlapi()
    iterator = h["getCmd"](
        h["SnmpEngine"](), _user_data(config), _target(config),
        h["ContextData"](), h["ObjectType"](h["ObjectIdentity"](oid)),
    )
    error_indication, error_status, error_index, var_binds = next(iterator)
    if error_indication:
        raise RuntimeError(str(error_indication))
    if error_status:
        raise RuntimeError(str(error_status))
    return [(str(name), value.prettyPrint()) for name, value in var_binds]


def test(config):
    values = dict(_request(config, "1.3.6.1.2.1.1.5.0"))
    return {"status": "online", "hostname": next(iter(values.values()), None)}


def discover_neighbors(config):
    """Collect the common LLDP and Cisco CDP neighbor tables via SNMP."""
    h = _hlapi()
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
            iterator = h["nextCmd"](
                h["SnmpEngine"](), _user_data(config), _target(config),
                h["ContextData"](), h["ObjectType"](h["ObjectIdentity"](oid)),
                lexicographicMode=False,
            )
            for error_indication, error_status, error_index, var_binds in iterator:
                if error_indication or error_status:
                    break
                for name, value in var_binds:
                    text_name = str(name)
                    if not text_name.startswith(oid + "."):
                        continue
                    index = text_name[len(oid) + 1:]
                    rows[index][field] = value.prettyPrint()
        for index, row in rows.items():
            if row.get("name") or row.get("port"):
                result.append({"protocol": protocol, "index": index, **row})
    return result
