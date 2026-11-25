"""Migrações do banco SQLite, numeradas e registradas na tabela `schema_versao`.

Para uma mudança nova no banco: crie uma função `_mN(conexao)` e acrescente
(N, "descrição", _mN) ao fim de MIGRACOES. Cada migração roda uma única vez, em
transação. Antes de aplicar migrações num banco que já tem dados, é feita uma
cópia de segurança em <pasta de dados>/backups/.
"""

from .relogio import utcnow
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger("netcable.migracoes")


def _colunas(conexao, tabela):
    return {c[1] for c in conexao.exec_driver_sql(f"PRAGMA table_info({tabela})")}


def _adicionar(conexao, tabela, colunas):
    existentes = _colunas(conexao, tabela)
    if not existentes:
        return  # table not created yet: create_all creates it with every column
    for coluna, ddl in colunas:
        if coluna not in existentes:
            conexao.exec_driver_sql(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {ddl}")


def _m1(conexao):
    """Colunas acrescentadas antes do sistema de migrações (bancos de versões antigas)."""
    _adicionar(conexao, "equipamentos", [
        ("monitor_mode", "VARCHAR DEFAULT 'ip'"), ("monitor_config", "VARCHAR"),
        ("notificar", "BOOLEAN NOT NULL DEFAULT 1"), ("rack_id", "VARCHAR"), ("rack_u", "INTEGER"),
        ("altura_u", "INTEGER"), ("modelo_id", "INTEGER"),
    ])
    if "share_token" not in _colunas(conexao, "projetos"):
        _adicionar(conexao, "projetos", [("share_token", "VARCHAR")])
        conexao.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_projetos_share_token ON projetos (share_token)")
    _adicionar(conexao, "projetos", [("user_id", "INTEGER")])
    # Usuários que já existiam (antes do modelo de equipe) viram admin.
    _adicionar(conexao, "usuarios", [
        ("papel", "VARCHAR NOT NULL DEFAULT 'admin'"), ("ativo", "BOOLEAN NOT NULL DEFAULT 1"),
        ("receber_alertas", "BOOLEAN NOT NULL DEFAULT 0"), ("relatorio_diario", "BOOLEAN NOT NULL DEFAULT 0"),
        ("relatorio_horario", "VARCHAR NOT NULL DEFAULT '08:00'"), ("ultimo_relatorio", "VARCHAR"),
        ("idioma", "VARCHAR NOT NULL DEFAULT 'en'"),
    ])


def _m2(conexao):
    """Uplink de cada equipamento (alertas por dependência). A tabela de manutenções é criada pelo create_all."""
    _adicionar(conexao, "equipamentos", [("depende_de", "VARCHAR")])


def _m3(conexao):
    """Atalhos entre mapas."""
    _adicionar(conexao, "equipamentos", [("mapa_destino_id", "INTEGER")])


def _m4(conexao):
    """2FA, manutenção agendada/recorrente e página de status pública."""
    _adicionar(conexao, "usuarios", [
        ("totp_segredo", "VARCHAR"), ("totp_ativo", "BOOLEAN NOT NULL DEFAULT 0"),
        ("totp_ultimo_passo", "INTEGER"), ("totp_recuperacao", "VARCHAR"),
    ])
    _adicionar(conexao, "manutencoes", [("inicio", "DATETIME"), ("recorrencia", "VARCHAR")])
    _adicionar(conexao, "equipamentos", [("status_publico", "BOOLEAN NOT NULL DEFAULT 1")])
    if "status_token" not in _colunas(conexao, "projetos"):
        _adicionar(conexao, "projetos", [("status_token", "VARCHAR")])
        conexao.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_projetos_status_token ON projetos (status_token)")


MIGRACOES = [
    (1, "colunas de versões anteriores ao sistema de migrações", _m1),
    (2, "uplink dos equipamentos (alertas por dependência)", _m2),
    (3, "atalhos entre mapas", _m3),
    (4, "2FA, manutenção agendada e página de status", _m4),
]


def versao_atual(conexao):
    conexao.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS schema_versao (versao INTEGER PRIMARY KEY, descricao VARCHAR, aplicada_em VARCHAR)"
    )
    linha = conexao.exec_driver_sql("SELECT MAX(versao) FROM schema_versao").fetchone()
    return linha[0] or 0


def _copia_de_seguranca(db_path, versao_destino):
    """Cópia consistente do banco antes de migrar (usa a API de backup do SQLite)."""
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return None
    pasta = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, f"pre-migracao-v{versao_destino}-{datetime.now():%Y%m%d-%H%M%S}.db")
    origem = sqlite3.connect(db_path)
    try:
        copia = sqlite3.connect(destino)
        with copia:
            origem.backup(copia)
        copia.close()
    finally:
        origem.close()
    return destino


def aplicar(engine, db_path):
    with engine.begin() as conexao:
        atual = versao_atual(conexao)
        tabelas = {r[0] for r in conexao.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        tem_dados = "usuarios" in tabelas and conexao.exec_driver_sql("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0
    pendentes = [m for m in MIGRACOES if m[0] > atual]
    if not pendentes:
        return atual
    if tem_dados:
        copia = _copia_de_seguranca(db_path, pendentes[-1][0])
        if copia:
            logger.info("Cópia de segurança antes de migrar: %s", copia)
    for versao, descricao, funcao in pendentes:
        with engine.begin() as conexao:
            funcao(conexao)
            conexao.exec_driver_sql(
                "INSERT INTO schema_versao (versao, descricao, aplicada_em) VALUES (?, ?, ?)",
                (versao, descricao, utcnow().isoformat()),
            )
        logger.info("Migração %s aplicada: %s", versao, descricao)
    return pendentes[-1][0]
