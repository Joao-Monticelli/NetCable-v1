"""Cable suggestions from LLDP/CDP: asks every SNMPv3 device of a map who its neighbors are and
matches them to the devices on the map (by management IP, then by name).

A cable seen from both ends (A says "B on my port 3", B says "A on my port 1") becomes one
suggestion. Neighbors that are not on the map are listed apart, so they can be added.
"""

import re
from concurrent.futures import ThreadPoolExecutor

MAX_EQUIPAMENTOS = 64


def normalizar_nome(nome):
    """'SW-Core.empresa.local' -> 'sw-core'; CDP ids like 'SW1(FOC1234X)' -> 'sw1'."""
    texto = (nome or "").strip().lower()
    texto = re.sub(r"\(.*?\)", "", texto).strip()
    if not re.fullmatch(r"\d+(\.\d+){3}", texto):
        texto = texto.split(".")[0]
    return re.sub(r"[^a-z0-9]+", "", texto)


def _porta(nome):
    return re.sub(r"\s+", "", (nome or "").lower())


def sugerir(equipamentos, conexoes, vizinhos_por_eq):
    """`equipamentos`: [{"id", "nome", "ip"}]; `conexoes`: [(source, target)];
    `vizinhos_por_eq`: {equipment id: [neighbors from snmp_service.discover_neighbors]}.
    Returns (suggestions, neighbors not on the map)."""
    por_ip = {}
    por_nome = {}
    repetidos = set()
    for e in equipamentos:
        if e.get("ip") and e["ip"] != "Sem IP":
            por_ip.setdefault(e["ip"].strip(), e["id"])
        chave = normalizar_nome(e.get("nome"))
        if chave:
            if chave in por_nome and por_nome[chave] != e["id"]:
                repetidos.add(chave)
            por_nome[chave] = e["id"]
    for chave in repetidos:
        por_nome.pop(chave)  # two devices with the same name: matching by name would be a guess
    nomes = {e["id"]: e.get("nome") for e in equipamentos}
    ligados = {frozenset(par) for par in conexoes if len(set(par)) == 2}

    sugestoes, fora = [], []
    for origem, vizinhos in vizinhos_por_eq.items():
        for v in vizinhos:
            destino = por_ip.get((v.get("address") or "").strip()) or por_nome.get(normalizar_nome(v.get("name")))
            if not destino:
                fora.append({"visto_por": nomes.get(origem), "visto_por_id": origem, "nome": v.get("name"), "ip": v.get("address"),
                             "porta": v.get("port"), "porta_local": v.get("local_port"), "plataforma": v.get("platform"),
                             "protocolo": v.get("protocol")})
                continue
            if destino == origem:
                continue
            portas = {origem: v.get("local_port"), destino: v.get("port")}
            par = frozenset((origem, destino))
            existente = next((s for s in sugestoes if frozenset((s["origem_id"], s["destino_id"])) == par and _mesmo_cabo(s, portas)), None)
            if existente:
                # The other end reported it too: fill in ports that were missing.
                for lado in ("origem", "destino"):
                    if not existente[f"porta_{lado}"]:
                        existente[f"porta_{lado}"] = portas.get(existente[f"{lado}_id"])
                if v.get("protocol") not in existente["protocolo"].split("+"):
                    existente["protocolo"] += "+" + v["protocol"]
                continue
            sugestoes.append({
                "origem_id": origem, "origem": nomes.get(origem), "porta_origem": portas[origem],
                "destino_id": destino, "destino": nomes.get(destino), "porta_destino": portas[destino],
                "protocolo": v.get("protocol") or "LLDP", "ja_ligado": par in ligados,
            })
    vistos = set()
    unicos = []
    for f in fora:  # the same unknown neighbor may be seen by several switches: keep each (who, port) once
        chave = (f["visto_por_id"], normalizar_nome(f["nome"]), f["ip"], _porta(f["porta_local"]))
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(f)
    return sugestoes, unicos


def _mesmo_cabo(sugestao, portas):
    """Same pair of devices: same cable unless both ends name different ports."""
    for lado in ("origem", "destino"):
        conhecida, nova = sugestao[f"porta_{lado}"], portas.get(sugestao[f"{lado}_id"])
        if conhecida and nova and _porta(conhecida) != _porta(nova):
            return False
    return True


def consultar(alvos, descobrir):
    """`alvos`: [(equipment id, SNMP config with host)]; `descobrir`: snmp_service.discover_neighbors.
    Returns ({id: neighbors}, {id: error message})."""
    vizinhos, erros = {}, {}

    def um(alvo):
        eq_id, config = alvo
        try:
            return eq_id, descobrir(config), None
        except Exception as exc:  # timeout, wrong credentials, SNMP not installed
            return eq_id, None, str(exc)[:200]

    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="netcable-lldp") as pool:
        for eq_id, lista, erro in pool.map(um, alvos[:MAX_EQUIPAMENTOS]):
            if erro:
                erros[eq_id] = erro
            else:
                vizinhos[eq_id] = lista
    return vizinhos, erros
