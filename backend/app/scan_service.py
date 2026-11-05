"""Lightweight LAN discovery: ping-sweep a /24 and read ARP MACs.

Designed for weak boxes (Pi 1): no nmap/arp-scan dependency, just ping3
(already required) plus /proc/net/arp. A 254-host sweep with 64 threads
takes ~5-15 seconds. Each device also gets a MAC-vendor guess (cached
IEEE OUI table) and a short TCP port hint for device-type guessing.
"""

import os
import socket
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import ping3

OUI_URL = "https://standards-oui.ieee.org/oui/oui.txt"
OUI_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "oui.txt")
OUI_MAX_AGE_DAYS = 30

# Short connect-scan: enough to guess the device class, fast on a LAN.
PROBE_PORTS = (22, 53, 80, 443, 445, 139, 8080, 8888, 5353)
PORT_TIMEOUT = 0.6


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


def _oui_table():
    """Return {OUI_PREFIX: vendor}. Downloads IEEE table once, caches on disk."""
    vendors = {}
    path = os.path.abspath(OUI_CACHE)
    stale = True
    if os.path.exists(path):
        age_days = (time.time() - os.path.getmtime(path)) / 86400
        stale = age_days > OUI_MAX_AGE_DAYS
    if stale:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            urllib.request.urlretrieve(OUI_URL, tmp)
            os.replace(tmp, path)
        except Exception:
            pass  # offline or slow link: fall back to whatever is cached
    try:
        with open(path, errors="ignore") as handle:
            for line in handle:
                if "(hex)" in line:
                    prefix, _, vendor = line.partition("(hex)")
                    vendors[prefix.strip().replace("-", ":")] = vendor.strip()
    except OSError:
        pass
    return vendors


def vendor_for(mac, table):
    if not mac:
        return None
    return table.get(mac.replace("-", ":").upper()[:8])


def _open_ports(ip, ports=PROBE_PORTS):
    open_ports = []
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(PORT_TIMEOUT)
        try:
            if sock.connect_ex((ip, port)) == 0:
                open_ports.append(port)
        except Exception:
            pass
        finally:
            sock.close()
    return open_ports


def guess_tipo(ip, open_ports, vendor=None):
    """Best-effort device class from gateway position, vendor and open ports."""
    try:
        last_octet = int(ip.rsplit(".", 1)[1])
    except ValueError:
        last_octet = -1
    if last_octet in (1, 254):
        return "router"
    v = (vendor or "").lower()
    if any(k in v for k in ("skyworth", "chuangwei", "tcl", "lg electronics", "vizio", "hisense", "philips", "panasonic", "roku", "chromecast", "google inc")):
        return "tv"
    if "samsung" in v:
        return "tv" if open_ports else "phone"
    if any(k in v for k in ("hewlett", "canon", "epson", "brother", "xerox", "lexmark", "kyocera")):
        return "printer"
    if any(k in v for k in ("hikvision", "dahua", "axis ", "hanwha", "uniview", "reolink", "amcrest", "foscam")):
        return "camera"
    if any(k in v for k in ("espressif", "tuya", "itead", "sonoff", "shelly", "aqara")):
        return "iot"
    if any(k in v for k in ("xiaomi", "oppo", "vivo", "oneplus", "realme", "motorola", "huawei", "honor", "nothing", "apple")):
        return "phone"
    if 445 in open_ports or 139 in open_ports:
        return "pc"
    if open_ports:
        return "server"
    return "unknown"


def guess_os(hostname, vendor, open_ports, tipo=None):
    """Best-effort OS/firmware label from hostname, vendor and open ports."""
    h = (hostname or "").lower()
    v = (vendor or "").lower()
    if h.startswith("android-") or "android" in h:
        return "Android"
    if "iphone" in h or "ipad" in h:
        return "iOS"
    if h.startswith("desktop-") or h.startswith("win-") or "desktop" in h:
        return "Windows"
    if "macbook" in h or "imac" in h or h.startswith("mac-"):
        return "macOS"
    if any(k in v for k in ("skyworth", "chuangwei", "tcl", "lg electronics", "vizio", "hisense", "philips", "panasonic", "roku")):
        return "Smart TV"
    if "samsung" in v:
        return "Smart TV" if open_ports else "Android"
    if any(k in v for k in ("hewlett", "canon", "epson", "brother", "xerox", "lexmark", "kyocera")):
        return "Printer"
    if any(k in v for k in ("hikvision", "dahua", "axis ", "hanwha", "uniview", "reolink", "amcrest", "foscam")):
        return "IP camera"
    if any(k in v for k in ("espressif", "tuya", "itead", "sonoff", "shelly", "aqara")):
        return "ESP firmware"
    if 445 in open_ports or 139 in open_ports:
        return "Windows"
    if "apple" in v:
        return "Apple device"
    if tipo == "router":
        return "Router"
    if tipo == "printer":
        return "Printer"
    if tipo == "camera":
        return "IP camera"
    if tipo == "tv":
        return "Smart TV"
    return None


def short_label(hostname, ip, mac, vendor):
    if hostname and hostname != ip:
        return hostname
    if vendor:
        suffix = "".join(mac.split(":")[3:]) if mac else ""
        name = vendor.split(",")[0].strip()[:20]
        return f"{name}-{suffix}" if suffix else name
    return ip


def scan_subnet(subnet=None, workers=64):
    """Return [{ip, mac, hostname, vendor, open_ports, tipo, status}]."""
    if not subnet:
        subnet = default_subnet()
    base = subnet.split("/")[0].rsplit(".", 1)[0]
    own = _own_ip()
    targets = [f"{base}.{i}" for i in range(1, 255) if f"{base}.{i}" != own]

    alive = set()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_ip = {pool.submit(_ping, ip): ip for ip in targets}
        for future in as_completed(future_to_ip):
            if future.result():
                alive.add(future_to_ip[future])

    macs = _arp_table()
    oui = _oui_table()
    found = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        host_futures = {pool.submit(_hostname, ip): ip for ip in sorted(alive)}
        port_futures = {pool.submit(_open_ports, ip): ip for ip in sorted(alive)}
        names = {}
        for future in as_completed(host_futures):
            try:
                names[host_futures[future]] = future.result(timeout=3)
            except Exception:
                names[host_futures[future]] = None
        ports = {}
        for future in as_completed(port_futures):
            try:
                ports[port_futures[future]] = future.result(timeout=30)
            except Exception:
                ports[port_futures[future]] = []
    for ip in sorted(alive, key=lambda a: tuple(int(p) for p in a.split("."))):
        mac = macs.get(ip)
        vendor = vendor_for(mac, oui)
        open_ports = ports.get(ip, [])
        tipo = guess_tipo(ip, open_ports, vendor)
        found.append({
            "ip": ip,
            "mac": mac,
            "hostname": names.get(ip) or ip,
            "vendor": vendor,
            "open_ports": open_ports,
            "tipo": tipo,
            "os": guess_os(names.get(ip) or ip, vendor, open_ports, tipo),
            "label": short_label(names.get(ip) or ip, ip, mac, vendor),
            "status": "online",
        })
    return {"subnet": subnet, "devices": found}
