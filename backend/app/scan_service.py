"""Lightweight LAN discovery: ping-sweep a /24 and read ARP MACs.

Designed for weak boxes (Pi 1): no nmap/arp-scan dependency, just ping3
(already required) plus /proc/net/arp. A 254-host sweep with 64 threads
takes ~5-15 seconds.
"""

import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

import ping3


def _own_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No packet is sent; only selects the source address.
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "192.168.0.1"
    finally:
        sock.close()


def default_subnet():
    ip = _own_ip()
    base = ".".join(ip.split(".")[:3])
    return f"{base}.0/24"


def _arp_table():
    macs = {}
    try:
        with open("/proc/net/arp") as handle:
            next(handle, None)  # header
            for line in handle:
                parts = line.split()
                if len(parts) >= 4 and ":" in parts[3]:
                    macs[parts[0]] = parts[3].upper()
    except OSError:
        pass
    return macs


def _ping(ip):
    try:
        return ping3.ping(ip, timeout=1) is not None
    except Exception:
        return False


def _hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0].split(".")[0]
    except Exception:
        return None


def scan_subnet(subnet=None, workers=64):
    """Return [{ip, mac, hostname, status}] for live hosts in the /24."""
    if not subnet:
        subnet = default_subnet()
    base = subnet.split("/")[0].rsplit(".", 1)[0]
    targets = [f"{base}.{i}" for i in range(1, 255)]

    alive = set()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_ip = {pool.submit(_ping, ip): ip for ip in targets}
        for future in as_completed(future_to_ip):
            if future.result():
                alive.add(future_to_ip[future])

    macs = _arp_table()
    found = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_ip = {pool.submit(_hostname, ip): ip for ip in sorted(alive)}
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                name = future.result(timeout=3)
            except Exception:
                name = None
            found.append({
                "ip": ip,
                "mac": macs.get(ip),
                "hostname": name or ip,
                "status": "online",
            })
    found.sort(key=lambda item: tuple(int(part) for part in item["ip"].split(".")))
    return {"subnet": subnet, "devices": found}
