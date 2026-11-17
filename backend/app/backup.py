"""Exportação/importação de mapas e backups completos do NetCable.

Formato de mapa (versão 2), estável e legível:
  {"formato": "netcable-mapa", "versao": 2, "projeto": {"nome": ...},
   "modelos": [...modelos usados...], "equipamentos": [...], "conexoes": [...]}
Senhas SNMP nunca vão para o arquivo.

Backup completo (.zip): netcable.db (cópia consistente), mapas/*.json, modelos.json e manifesto.json.
"""

import io
import json
import os
import re
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone

from . import crud, models

FORMATO = "netcable-mapa"
VERSAO = 2
PADRAO_ARQUIVO = re.compile(r"^netcable-backup-\d{8}-\d{6}\.zip$")
CAMPOS_MODELO = ("nome", "fabricante", "tipo", "altura_u", "portas_rj45", "portas_sfp", "prefixo_porta")
SNMP_SEM_SENHA = ("username", "authProtocol", "privProtocol", "port")


# --------------------------------------------------------------------------- exportar
def exportar_projeto(db, projeto, abrir_config, versao_app="dev"):
    modelos_por_id = {m.id: m for m in crud.listar_modelos(db)}
    usados = {}
    equipamentos = []
    for eq in projeto.equipamentos:
        modelo = modelos_por_id.get(eq.modelo_id)
        if modelo:
            usados[modelo.nome] = {c: getattr(modelo, c) for c in CAMPOS_MODELO}
        snmp = {k: v for k, v in abrir_config(eq.monitor_config).items() if k in SNMP_SEM_SENHA} if eq.monitor_mode == "snmpv3" else None
        equipamentos.append({
            "id": eq.id, "nome": eq.nome, "ip": eq.ip, "tipo": eq.tipo,
            "pos_x": eq.pos_x, "pos_y": eq.pos_y, "width": eq.width, "height": eq.height,
            "monitor_mode": eq.monitor_mode or "ip", "snmp": snmp, "notificar": eq.notificar,
            "rack_id": eq.rack_id, "rack_u": eq.rack_u, "altura_u": eq.altura_u,
            "modelo": modelo.nome if modelo else None, "depende_de": eq.depende_de,
        })
    conexoes = db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto.id).all()
    return {
        "formato": FORMATO, "versao": VERSAO, "app_versao": versao_app,
        "exportado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "projeto": {"nome": projeto.nome},
        "modelos": list(usados.values()),
        "equipamentos": equipamentos,
        "conexoes": [{"id": c.id, "source": c.source, "target": c.target, "label": c.label,
                      "source_handle": c.source_handle, "target_handle": c.target_handle} for c in conexoes],
    }


# --------------------------------------------------------------------------- importar
def _de_formato_v1(dados):
    """Arquivos exportados pelas versões antigas (nós do React Flow)."""
    equipamentos = []
    for no in dados.get("equipamentos", []):
        d = no.get("data") or {}
        estilo = no.get("style") or {}
        rack = no.get("type") == "rack" or d.get("tipo") == "Rack"
        snmp = d.get("snmpConfig") or None
        equipamentos.append({
            "id": no["id"], "nome": d.get("label") or "?", "ip": d.get("ip") or "Sem IP", "tipo": "Rack" if rack else (d.get("tipo") or "Servidor"),
            "pos_x": (no.get("position") or {}).get("x", 0), "pos_y": (no.get("position") or {}).get("y", 0),
            "width": estilo.get("width") or 200, "height": estilo.get("height") or 80,
            "monitor_mode": d.get("monitorMode") or "ip",
            "snmp": {k: v for k, v in snmp.items() if k in SNMP_SEM_SENHA} if isinstance(snmp, dict) and snmp else None,
            "notificar": d.get("notificar", True) is not False,
            "rack_id": no.get("parentNode"), "rack_u": d.get("rackU"), "altura_u": d.get("us") if rack else d.get("alturaU"),
            "modelo": None,
        })
    conexoes = [{"id": e["id"], "source": e["source"], "target": e["target"], "label": e.get("label"),
                 "source_handle": e.get("sourceHandle"), "target_handle": e.get("targetHandle")} for e in dados.get("conexoes", [])]
    return {"projeto": {"nome": dados.get("projeto") or "Mapa importado"}, "modelos": [], "equipamentos": equipamentos, "conexoes": conexoes}


def normalizar_arquivo(dados):
    if not isinstance(dados, dict):
        raise ValueError("Arquivo de mapa inválido.")
    if dados.get("formato") == FORMATO:
        if int(dados.get("versao", 0)) > VERSAO:
            raise ValueError("Arquivo criado por uma versão mais nova do NetCable.")
        return dados
    if isinstance(dados.get("equipamentos"), list) and isinstance(dados.get("conexoes"), list):
        return _de_formato_v1(dados)
    raise ValueError("Arquivo de mapa inválido.")


def _nome_livre(db, nome):
    existentes = {p.nome for p in crud.get_projetos(db)}
    if nome not in existentes:
        return nome
    n = 2
    while f"{nome} ({n})" in existentes:
        n += 1
    return f"{nome} ({n})"


def importar_mapa(db, dados, user_id, proteger_config):
    """Cria um projeto NOVO a partir do arquivo (não sobrescreve nada).
    IDs são trocados por novos, então o mesmo arquivo pode ser importado várias vezes."""
    dados = normalizar_arquivo(dados)
    modelos_criados = 0
    ids_modelo = {}
    for m in dados.get("modelos", []):
        existente = crud.get_modelo_por_nome(db, m["nome"])
        if not existente:
            existente = crud.salvar_modelo(db, {c: m.get(c) for c in CAMPOS_MODELO if c in m})
            modelos_criados += 1
        ids_modelo[m["nome"]] = existente.id

    sufixo = uuid.uuid4().hex[:8]
    novo_id = {eq["id"]: f"{eq['id']}-{sufixo}" for eq in dados["equipamentos"]}
    projeto = crud.criar_projeto(db, _nome_livre(db, (dados.get("projeto") or {}).get("nome") or "Mapa importado"), user_id)
    try:
        return _preencher_projeto(db, projeto, dados, novo_id, sufixo, ids_modelo, modelos_criados, proteger_config)
    except Exception:
        db.rollback()
        crud.deletar_projeto(db, projeto.id)  # nada de projeto pela metade
        raise


def _preencher_projeto(db, projeto, dados, novo_id, sufixo, ids_modelo, modelos_criados, proteger_config):
    equipamentos = []
    for eq in dados["equipamentos"]:
        visual = eq.get("monitor_mode") == "visual" or eq.get("ip") == "Sem IP" or eq.get("tipo") == "Rack"
        equipamentos.append({
            "id": novo_id[eq["id"]], "nome": eq["nome"], "ip": eq.get("ip") or "Sem IP", "tipo": eq.get("tipo") or "Servidor",
            "status": "visual" if visual else "offline", "pingTime": None,
            "posX": eq.get("pos_x", 0), "posY": eq.get("pos_y", 0), "width": eq.get("width") or 200, "height": eq.get("height") or 80,
            "monitorMode": eq.get("monitor_mode") or "ip",
            "monitorConfig": proteger_config(eq["snmp"]) if eq.get("snmp") else None,
            "notificar": eq.get("notificar", True) is not False,
            "rackId": novo_id.get(eq.get("rack_id")) if eq.get("rack_id") else None,
            "rackU": eq.get("rack_u"), "alturaU": eq.get("altura_u"),
            "modeloId": ids_modelo.get(eq.get("modelo")),
            "dependeDe": novo_id.get(eq.get("depende_de")) if eq.get("depende_de") else None,
        })
    erro = crud.validar_racks(equipamentos)
    if erro:
        raise ValueError(erro)
    conexoes = [{
        "id": f"{c['id']}-{sufixo}", "source": novo_id[c["source"]], "target": novo_id[c["target"]], "label": c.get("label"),
        "sourceHandle": c.get("source_handle"), "targetHandle": c.get("target_handle"),
    } for c in dados["conexoes"] if c.get("source") in novo_id and c.get("target") in novo_id]
    crud.salvar_mapa(db, projeto.id, equipamentos, conexoes)
    return {"id": projeto.id, "nome": projeto.nome, "equipamentos": len(equipamentos), "conexoes": len(conexoes), "modelos_criados": modelos_criados}


def importar_arquivo(db, conteudo: bytes, user_id, proteger_config):
    """Aceita um mapa (.json) ou um backup completo (.zip, importa todos os mapas dele)."""
    if conteudo[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            nomes = sorted(n for n in z.namelist() if n.startswith("mapas/") and n.endswith(".json"))
            if not nomes:
                raise ValueError("O backup não contém mapas.")
            importados = []
            try:
                for n in nomes:
                    importados.append(importar_mapa(db, json.loads(z.read(n)), user_id, proteger_config))
            except Exception:
                for item in importados:  # tudo ou nada
                    crud.deletar_projeto(db, item["id"])
                raise
            return importados
    try:
        dados = json.loads(conteudo.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Arquivo de mapa inválido.")
    return [importar_mapa(db, dados, user_id, proteger_config)]


# --------------------------------------------------------------------------- backup completo
def _nome_arquivo(texto):
    return re.sub(r"[^\w.-]+", "_", texto, flags=re.UNICODE).strip("_")[:60] or "mapa"


def criar_backup(db, db_path, diretorio, abrir_config, versao_app="dev"):
    os.makedirs(diretorio, exist_ok=True)
    destino = os.path.join(diretorio, f"netcable-backup-{datetime.now():%Y%m%d-%H%M%S}.zip")
    temporario = destino + ".tmp"
    copia_db = destino + ".db.tmp"
    origem = sqlite3.connect(db_path)
    try:
        copia = sqlite3.connect(copia_db)
        with copia:
            origem.backup(copia)  # cópia consistente mesmo com o NetCable rodando
        copia.close()
    finally:
        origem.close()
    projetos = crud.get_projetos(db)
    try:
        with zipfile.ZipFile(temporario, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copia_db, "netcable.db")
            for p in projetos:
                z.writestr(f"mapas/{p.id:04d}-{_nome_arquivo(p.nome)}.json",
                           json.dumps(exportar_projeto(db, p, abrir_config, versao_app), ensure_ascii=False, indent=2))
            z.writestr("modelos.json", json.dumps([{c: getattr(m, c) for c in CAMPOS_MODELO} for m in crud.listar_modelos(db)], ensure_ascii=False, indent=2))
            z.writestr("manifesto.json", json.dumps({
                "app": "NetCable", "app_versao": versao_app, "criado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "mapas": len(projetos), "conteudo": ["netcable.db", "mapas/*.json", "modelos.json"],
                "restaurar": "Mapas: importe este .zip pela tela de projetos. Tudo (usuários, histórico): pare o NetCable e substitua data/netcable.db pelo netcable.db deste arquivo.",
            }, ensure_ascii=False, indent=2))
        os.replace(temporario, destino)
    finally:
        for f in (copia_db, temporario):
            if os.path.exists(f):
                os.remove(f)
    return destino


def listar_backups(diretorio):
    if not os.path.isdir(diretorio):
        return []
    itens = []
    for nome in os.listdir(diretorio):
        if PADRAO_ARQUIVO.match(nome):
            caminho = os.path.join(diretorio, nome)
            itens.append({"nome": nome, "tamanho": os.path.getsize(caminho),
                          "criado_em": datetime.fromtimestamp(os.path.getmtime(caminho), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    return sorted(itens, key=lambda i: i["nome"], reverse=True)


def limpar_antigos(diretorio, manter):
    apagados = 0
    for item in listar_backups(diretorio)[max(1, manter):]:
        os.remove(os.path.join(diretorio, item["nome"]))
        apagados += 1
    return apagados


def testar_diretorio(diretorio):
    """Garante que a pasta existe e aceita escrita; levanta OSError se não."""
    os.makedirs(diretorio, exist_ok=True)
    teste = os.path.join(diretorio, f".netcable-teste-{uuid.uuid4().hex[:6]}")
    with open(teste, "w") as f:
        f.write("ok")
    os.remove(teste)
