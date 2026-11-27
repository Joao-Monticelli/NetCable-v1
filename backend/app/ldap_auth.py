"""Login with the company directory: LDAP or Active Directory (ldap3).

The admin sets it in ⚙️ → Directory (LDAP/AD). When someone logs in with a name that is not a
local NetCable account, NetCable:
  1. binds with the service account (or anonymously) and searches `filtro` under `base_dn`;
  2. binds as the user found, with the password typed (so the directory checks it);
  3. picks the role from the user's groups (admin > editor > viewer), or `papel_padrao`;
  4. creates or updates the NetCable user (origem="ldap"); the password is never stored.

Groups are read from `memberOf` (Active Directory, OpenLDAP with the memberof overlay) or, when the
entry has none, from groups that list the user in member / uniqueMember / memberUid.
Local accounts (like the admin made at first run) keep working, so a directory outage never
locks everybody out.
"""

import logging
import ssl
from urllib.parse import urlparse

from . import crud

logger = logging.getLogger("netcable.ldap")

PREFIXO = "ldap."
FILTRO_PADRAO = "(&(objectClass=person)(|(sAMAccountName={usuario})(uid={usuario})(userPrincipalName={usuario})))"
CAMPOS = ("ativo", "servidor", "starttls", "verificar_cert", "bind_dn", "bind_senha", "base_dn", "filtro",
          "atributo_email", "grupo_admin", "grupo_editor", "grupo_visualizador", "papel_padrao")
PAPEIS_PADRAO = ("", "visualizador", "editor")
TIMEOUT = 5


class ErroLdap(RuntimeError):
    """The directory could not be reached or answered with an error (not a wrong password)."""


def _sim(valor):
    return str(valor).strip().lower() in ("1", "true", "yes", "sim")


def ler_config(db, abrir=None):
    """Settings with the service password in clear (`abrir` decrypts it; see nucleo.abrir_config)."""
    cfg = crud.get_configuracoes(db, PREFIXO)
    dados = {campo: cfg.get(PREFIXO + campo) or "" for campo in CAMPOS}
    dados["ativo"] = _sim(dados["ativo"])
    dados["starttls"] = _sim(dados["starttls"])
    dados["verificar_cert"] = dados["verificar_cert"] == "" or _sim(dados["verificar_cert"])  # on unless turned off
    dados["filtro"] = dados["filtro"] or FILTRO_PADRAO
    dados["atributo_email"] = dados["atributo_email"] or "mail"
    if dados["bind_senha"] and abrir:
        dados["bind_senha"] = abrir(dados["bind_senha"]).get("v", "")
    return dados


def _servidor(cfg):
    from ldap3 import Server, Tls
    url = urlparse(cfg["servidor"] if "://" in cfg["servidor"] else "ldap://" + cfg["servidor"])
    if url.scheme not in ("ldap", "ldaps") or not url.hostname:
        raise ErroLdap("Endereço do servidor inválido (use ldap://servidor ou ldaps://servidor).")
    seguro = url.scheme == "ldaps"
    tls = Tls(validate=ssl.CERT_REQUIRED if cfg["verificar_cert"] else ssl.CERT_NONE) if (seguro or cfg["starttls"]) else None
    return Server(url.hostname, port=url.port or (636 if seguro else 389), use_ssl=seguro, tls=tls,
                  get_info="NO_INFO", connect_timeout=TIMEOUT)


def conectar(cfg, usuario=None, senha=None):
    """Opens and binds a connection. Returns (connection, bound). Tests replace this function."""
    from ldap3 import Connection
    from ldap3.core.exceptions import LDAPException
    try:
        conexao = Connection(_servidor(cfg), user=usuario or None, password=senha or None,
                             receive_timeout=TIMEOUT, raise_exceptions=False, read_only=True)
        conexao.open()
        if conexao.closed:
            raise ErroLdap("Sem resposta do servidor LDAP.")
        if cfg["starttls"] and not conexao.start_tls():
            raise ErroLdap(f"Falha no STARTTLS: {conexao.result.get('description') if conexao.result else ''}")
        return conexao, bool(conexao.bind())
    except LDAPException as exc:
        raise ErroLdap(str(exc)) from exc


def _normalizar_dn(dn):
    return ",".join(parte.strip() for parte in str(dn).lower().split(","))


def _pertence(grupos, configurado):
    """`configurado` may be a full DN (cn=NetCable-Admins,ou=Groups,dc=example,dc=com) or only the group name."""
    configurado = (configurado or "").strip()
    if not configurado:
        return False
    if "=" in configurado:
        alvo = _normalizar_dn(configurado)
        return any(_normalizar_dn(g) == alvo for g in grupos)
    nome = configurado.lower()
    return any(_normalizar_dn(g).split(",")[0].split("=", 1)[-1] == nome for g in grupos)


def papel_dos_grupos(cfg, grupos):
    for papel, campo in (("admin", "grupo_admin"), ("editor", "grupo_editor"), ("visualizador", "grupo_visualizador")):
        if _pertence(grupos, cfg.get(campo)):
            return papel
    return cfg.get("papel_padrao") or None


def _valores(entrada, atributo):
    try:
        valor = entrada[atributo].value
    except (KeyError, IndexError, AttributeError):
        return []
    if valor is None:
        return []
    return [str(v) for v in valor] if isinstance(valor, (list, tuple)) else [str(valor)]


def buscar(cfg, username):
    """Finds the user. Returns {"dn", "email", "grupos"} or None. Raises ErroLdap if the directory fails."""
    from ldap3 import SUBTREE
    from ldap3.utils.conv import escape_filter_chars
    if not cfg["servidor"] or not cfg["base_dn"]:
        raise ErroLdap("Configure o servidor e a base de busca (base DN).")
    conexao, ligado = conectar(cfg, cfg["bind_dn"], cfg["bind_senha"])
    try:
        if not ligado:
            raise ErroLdap("A conta de serviço (bind DN) foi recusada pelo diretório.")
        filtro = cfg["filtro"].replace("{usuario}", escape_filter_chars(username))
        conexao.search(cfg["base_dn"], filtro, SUBTREE, attributes=[cfg["atributo_email"], "memberOf"], size_limit=2)
        if conexao.result and conexao.result.get("result") not in (0, 4, None):  # 4 = size limit exceeded
            raise ErroLdap(f"Busca recusada: {conexao.result.get('description')}")
        entradas = list(conexao.entries)
        if not entradas:
            return None
        if len(entradas) > 1:
            raise ErroLdap(f"Mais de uma conta no diretório responde por '{username}': ajuste o filtro.")
        entrada = entradas[0]
        dn = entrada.entry_dn
        grupos = _valores(entrada, "memberOf")
        if not grupos:
            dn_escapado = escape_filter_chars(dn)
            conexao.search(cfg["base_dn"], f"(|(member={dn_escapado})(uniqueMember={dn_escapado})(memberUid={escape_filter_chars(username)}))",
                           SUBTREE, attributes=["cn"])
            grupos = [g.entry_dn for g in conexao.entries]
        emails = _valores(entrada, cfg["atributo_email"])
        return {"dn": dn, "email": emails[0] if emails else None, "grupos": grupos}
    finally:
        conexao.unbind()


def autenticar(cfg, username, senha):
    """Returns the user info plus "papel" (None = in no allowed group) when the password is right,
    None when the user does not exist or the password is wrong. Raises ErroLdap if the directory fails."""
    if not senha:
        return None  # an LDAP bind with an empty password is an "unauthenticated bind" and succeeds
    info = buscar(cfg, username)
    if not info:
        return None
    conexao, ligado = conectar(cfg, info["dn"], senha)
    try:
        if not ligado:
            return None
    finally:
        conexao.unbind()
    info["papel"] = papel_dos_grupos(cfg, info["grupos"])
    return info
