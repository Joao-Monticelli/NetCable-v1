"""Descoberta da rede: varre uma faixa de IPs e lista quem respondeu.

Fase 1 (quem está vivo): ICMP + TCP 80/443/22 em paralelo para todos os endereços.
Fase 2 (só os vivos): portas comuns (para sugerir o tipo) e nome reverso (DNS/PTR).

Por segurança só aceita faixas privadas (RFC 1918, CGNAT, link-local) de até 1024
endereços; DISCOVERY_ALLOW_PUBLIC=1 libera faixas públicas (ex.: laboratório).
"""

import ipaddress
import os
import socket
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import ping3

MAX_ENDERECOS = 1024
TIMEOUT = float(os.getenv("DISCOVERY_TIMEOUT", "0.8"))
PORTAS_VIDA = (80, 443, 22)
PORTAS_EXTRAS = (53, 139, 445, 3389, 5000, 5001, 8006, 8080, 9100, 554, 161)
WORKERS = int(os.getenv("DISCOVERY_WORKERS", "128"))
CGNAT = ipaddress.ip_network("100.64.0.0/10")
EXPIRA_S = 15 * 60

_jobs = {}
_trava = threading.Lock()


# --------------------------------------------------------------------------- validação
def validar_faixa(texto):
    """Devolve a lista de IPs (str) da faixa ou levanta ValueError com mensagem amigável.
    Aceita CIDR (192.168.1.0/24), intervalo (192.168.1.10-192.168.1.50) ou um IP."""
    texto = (texto or "").strip()
    try:
        if "-" in texto:
            ini, fim = (ipaddress.ip_address(p.strip()) for p in texto.split("-", 1))
            if ini.version != 4 or fim.version != 4 or int(fim) < int(ini):
                raise ValueError
            ips = [ipaddress.ip_address(i) for i in range(int(ini), int(fim) + 1)] if int(fim) - int(ini) < MAX_ENDERECOS else None
            if ips is None:
                raise OverflowError
        else:
            rede = ipaddress.ip_network(texto, strict=False)
            if rede.version != 4:
                raise ValueError
            if rede.num_addresses > MAX_ENDERECOS + 2:
                raise OverflowError
            ips = list(rede.hosts()) if rede.num_addresses > 2 else list(rede)
    except OverflowError:
        raise ValueError(f"Faixa grande demais: use no máximo {MAX_ENDERECOS} endereços (ex.: /22).")
    except ValueError:
        raise ValueError("Faixa inválida. Use, por exemplo, 192.168.1.0/24 ou 192.168.1.10-192.168.1.50.")
    publico_ok = os.getenv("DISCOVERY_ALLOW_PUBLIC", "").strip() in ("1", "true", "yes")
    if not publico_ok and not all(ip.is_private or ip in CGNAT for ip in (ips[0], ips[-1])):
        raise ValueError("Só é possível varrer redes privadas (ex.: 192.168.x.x, 10.x.x.x, 172.16-31.x.x).")
    return [str(ip) for ip in ips]


# --------------------------------------------------------------------------- sondas
def sonda_tcp(ip, porta, timeout=None):
    try:
        with socket.create_connection((ip, porta), timeout=timeout or TIMEOUT):
            return True
    except ConnectionRefusedError:
        return "recusada"  # o host respondeu (RST): está vivo, porta fechada
    except OSError:
        return False


def sonda_icmp(ip):
    try:
        r = ping3.ping(ip, timeout=TIMEOUT)
        return r not in (None, False)
    except Exception:
        return False


def nome_reverso(ip):
    try:
        nome = socket.gethostbyaddr(ip)[0]
        return nome if nome and nome != ip else None
    except OSError:
        return None


def ler_tabela_arp():
    """MACs vistos pelo sistema (Linux). Num container em modo bridge normalmente fica vazio."""
    macs = {}
    try:
        with open("/proc/net/arp") as f:
            next(f, None)
            for linha in f:
                partes = linha.split()
                if len(partes) >= 4 and partes[3] != "00:00:00:00:00:00":
                    macs[partes[0]] = partes[3].upper()
    except OSError:
        pass
    return macs


def sugerir_tipo(ip, portas):
    """Palpite do tipo pelo conjunto de portas abertas (o usuário pode trocar antes de adicionar)."""
    p = set(portas)
    if p & {9100}:
        return "Impressora"
    if p & {5000, 5001} or ({445, 139} & p and {80, 443} & p and 3389 not in p):
        return "Storage/NAS"
    if 3389 in p or (p & {445, 139} and not p & {22}):
        return "PC"
    if 554 in p:
        return "Câmera"
    if 53 in p or ip.endswith(".1") or ip.endswith(".254"):
        return "Roteador"
    if 8006 in p or 22 in p:
        return "Servidor"
    return "Servidor"


# --------------------------------------------------------------------------- execução
def _executar(job, ips, sondas):
    tcp, icmp, rdns = sondas["tcp"], sondas["icmp"], sondas["rdns"]
    vivos = {}
    with ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="netcable-descoberta") as pool:
        # Fase 1: quem está vivo
        tarefas = {}
        for ip in ips:
            tarefas[pool.submit(icmp, ip)] = (ip, None)
            for porta in PORTAS_VIDA:
                tarefas[pool.submit(tcp, ip, porta)] = (ip, porta)
        restantes = {ip: 1 + len(PORTAS_VIDA) for ip in ips}
        for futuro in as_completed(tarefas):
            if job["cancelado"]:
                break
            ip, porta = tarefas[futuro]
            r = futuro.result()
            if r:
                info = vivos.setdefault(ip, {"portas": set()})
                if r is True and porta:
                    info["portas"].add(porta)
            restantes[ip] -= 1
            if restantes[ip] == 0:
                job["verificados"] += 1
        # Fase 2: detalhes dos vivos
        job["fase"] = "detalhes"
        tarefas = {}
        for ip in vivos:
            tarefas[pool.submit(rdns, ip)] = (ip, "nome")
            for porta in PORTAS_EXTRAS:
                if porta != 161:
                    tarefas[pool.submit(tcp, ip, porta)] = (ip, porta)
        for futuro in as_completed(tarefas):
            if job["cancelado"]:
                break
            ip, oque = tarefas[futuro]
            r = futuro.result()
            if oque == "nome":
                vivos[ip]["nome"] = r
            elif r is True:
                vivos[ip]["portas"].add(oque)
    macs = ler_tabela_arp()
    chave = lambda ip: tuple(int(x) for x in ip.split("."))
    job["resultados"] = [{
        "ip": ip, "nome": info.get("nome"), "mac": macs.get(ip), "portas": sorted(info["portas"]),
        "tipo_sugerido": sugerir_tipo(ip, info["portas"]),
    } for ip, info in sorted(vivos.items(), key=lambda kv: chave(kv[0]))]
    job["status"] = "cancelado" if job["cancelado"] else "concluido"
    job["fim"] = time.time()


def iniciar(ips, user_id, sondas=None, em_segundo_plano=True):
    sondas = sondas or {"tcp": sonda_tcp, "icmp": sonda_icmp, "rdns": nome_reverso}
    _limpar_antigos()
    with _trava:
        if any(j["user_id"] == user_id and j["status"] == "rodando" for j in _jobs.values()):
            raise RuntimeError("Já existe uma varredura em andamento.")
        job = {"id": uuid.uuid4().hex[:12], "user_id": user_id, "status": "rodando", "fase": "vivos", "total": len(ips),
               "verificados": 0, "resultados": [], "inicio": time.time(), "fim": None, "cancelado": False, "erro": None}
        _jobs[job["id"]] = job

    def rodar():
        try:
            _executar(job, ips, sondas)
        except Exception as exc:  # nunca deixa o job "rodando" para sempre
            job["status"], job["erro"], job["fim"] = "erro", str(exc), time.time()

    if em_segundo_plano:
        threading.Thread(target=rodar, name="netcable-descoberta-job", daemon=True).start()
    else:
        rodar()
    return job


def obter(job_id, user_id):
    job = _jobs.get(job_id)
    if not job or job["user_id"] != user_id:
        return None
    return job


def cancelar(job_id, user_id):
    job = obter(job_id, user_id)
    if job and job["status"] == "rodando":
        job["cancelado"] = True
    return job


def _limpar_antigos():
    agora = time.time()
    with _trava:
        for jid in [j for j, job in _jobs.items() if job["fim"] and agora - job["fim"] > EXPIRA_S]:
            _jobs.pop(jid, None)
