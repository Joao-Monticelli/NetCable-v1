"""Login with LDAP / Active Directory against an in-memory directory (ldap3 MOCK_SYNC)."""
import pytest

from app import crud, ldap_auth, models

BASE = "dc=empresa,dc=local"
ADMINS = f"cn=NetCable-Admins,ou=Grupos,{BASE}"


@pytest.fixture()
def diretorio(monkeypatch):
    from ldap3 import MOCK_SYNC, Connection, Server
    servidor = Server("mock-ad")
    raiz = Connection(servidor, client_strategy=MOCK_SYNC)
    add = raiz.strategy.add_entry
    add(f"cn=svc-netcable,{BASE}", {"objectClass": "person", "userPassword": "svc-senha"})
    # Active Directory style: memberOf on the user
    add(f"cn=Ana Souza,ou=TI,{BASE}", {"objectClass": "person", "sAMAccountName": "ana", "userPassword": "senha-ana",
                                       "mail": "ana@empresa.local", "memberOf": [ADMINS]})
    # OpenLDAP style: no memberOf, listed as member of a groupOfNames
    add(f"uid=bruno,ou=TI,{BASE}", {"objectClass": "person", "uid": "bruno", "userPassword": "senha-bruno"})
    add(f"cn=netcable-editores,ou=Grupos,{BASE}", {"objectClass": "groupOfNames", "member": [f"uid=bruno,ou=TI,{BASE}"]})
    # In no NetCable group
    add(f"cn=Carla,ou=RH,{BASE}", {"objectClass": "person", "sAMAccountName": "carla", "userPassword": "senha-carla"})
    # A directory account with the same name as a local NetCable account
    add(f"cn=Local,ou=TI,{BASE}", {"objectClass": "person", "sAMAccountName": "ldap-local", "userPassword": "senha-diretorio"})
    estado = {"fora": False}

    def conectar(cfg, usuario=None, senha=None):
        if estado["fora"]:
            raise ldap_auth.ErroLdap("socket timeout")
        c = Connection(servidor, user=usuario, password=senha, client_strategy=MOCK_SYNC)
        c.strategy.entries = raiz.strategy.entries
        return c, bool(c.bind())

    monkeypatch.setattr(ldap_auth, "conectar", conectar)
    return estado


def _login(c, usuario, senha):
    return c.post("/api/login", data={"username": usuario, "password": senha}, headers={"Authorization": ""})


@pytest.fixture()
def ldap_ligado(cliente, diretorio):
    c, db = cliente
    r = c.put("/api/config/ldap", json={
        "ativo": True, "servidor": "ldaps://dc01.empresa.local", "bind_dn": f"cn=svc-netcable,{BASE}", "bind_senha": "svc-senha",
        "base_dn": BASE, "grupo_admin": ADMINS, "grupo_editor": "netcable-editores",
    })
    assert r.status_code == 200, r.text
    yield c, db, diretorio
    from app.rotas.contas import login_failures
    login_failures.clear()
    for nome in ("ana", "bruno", "carla", "ldap-local"):
        u = crud.get_usuario(db, nome)
        if u:
            db.delete(u)
    db.query(models.Configuracao).filter(models.Configuracao.chave.like("ldap.%")).delete(synchronize_session=False)
    db.query(models.Auditoria).delete()
    db.commit()


def test_config_ldap_valida_e_esconde_a_senha(cliente):
    c, db = cliente
    try:
        assert c.put("/api/config/ldap", json={"ativo": True, "servidor": "", "base_dn": BASE}).status_code == 400
        assert c.put("/api/config/ldap", json={"servidor": "ldap://dc01", "filtro": "(uid=fixo)"}).status_code == 400
        assert c.put("/api/config/ldap", json={"servidor": "ldap://dc01 ; rm", "base_dn": BASE}).status_code == 400
        assert c.put("/api/config/ldap", json={"servidor": "ldap://dc01", "papel_padrao": "admin"}).status_code == 400
        r = c.put("/api/config/ldap", json={"ativo": True, "servidor": "ldap://dc01:3268", "base_dn": BASE, "bind_senha": "segredo"})
        dados = r.json()
        assert dados["ativo"] and dados["bind_senha_definida"] and "bind_senha" not in dados
        assert dados["filtro"] == ldap_auth.FILTRO_PADRAO and dados["verificar_cert"]
        guardado = db.get(models.Configuracao, "ldap.bind_senha").valor
        assert "segredo" not in guardado  # encrypted
        # None keeps the password, "" removes it
        assert c.put("/api/config/ldap", json={"servidor": "ldap://dc01", "base_dn": BASE}).json()["bind_senha_definida"]
        assert not c.put("/api/config/ldap", json={"servidor": "ldap://dc01", "base_dn": BASE, "bind_senha": ""}).json()["bind_senha_definida"]
    finally:
        db.query(models.Configuracao).filter(models.Configuracao.chave.like("ldap.%")).delete(synchronize_session=False)
        db.commit()


def test_login_pelo_diretorio_cria_usuario_com_papel_dos_grupos(ldap_ligado):
    c, db, _ = ldap_ligado
    assert _login(c, "ana", "errada").status_code == 400
    assert _login(c, "ana", "").status_code in (400, 422)  # empty password never reaches a bind
    r = _login(c, "Ana", "senha-ana")
    assert r.status_code == 200, r.text
    ana = crud.get_usuario(db, "ana")
    assert ana.origem == "ldap" and ana.papel == "admin" and ana.email == "ana@empresa.local"
    me = c.get("/api/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert me["origem"] == "ldap" and me["username"] == "ana"

    r = _login(c, "bruno", "senha-bruno")  # group by name, membership from groupOfNames
    assert r.status_code == 200 and crud.get_usuario(db, "bruno").papel == "editor"

    assert _login(c, "carla", "senha-carla").status_code == 403  # in no allowed group
    c.put("/api/config/ldap", json={**c.get("/api/config/ldap").json(), "papel_padrao": "visualizador"})
    assert _login(c, "carla", "senha-carla").status_code == 200
    assert crud.get_usuario(db, "carla").papel == "visualizador"

    acoes = [a.acao for a in db.query(models.Auditoria).all()]
    assert "login.ldap_sem_grupo" in acoes and acoes.count("usuario.criado") == 3


def test_papel_acompanha_o_diretorio_e_senha_local_nao_existe(ldap_ligado):
    c, db, _ = ldap_ligado
    from app import main
    token = _login(c, "bruno", "senha-bruno").json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert c.put("/api/me/perfil", json={"senha_atual": "senha-bruno", "nova_senha": "outra-senha-1"}, headers=h).status_code == 400
    bruno = crud.get_usuario(db, "bruno")
    assert c.put(f"/api/usuarios/{bruno.id}", json={"nova_senha": "outra-senha-1"}).status_code == 400
    # The random local hash never works, even with the directory turned off
    assert not main.pwd_context.verify("senha-bruno", bruno.password_hash)
    # Moved to the admins group in the directory: the next login updates the role
    c.put("/api/config/ldap", json={**c.get("/api/config/ldap").json(), "grupo_admin": "netcable-editores", "grupo_editor": ""})
    assert _login(c, "bruno", "senha-bruno").status_code == 200
    db.refresh(bruno)
    assert bruno.papel == "admin"
    # An admin can still disable a directory user in NetCable
    c.put(f"/api/usuarios/{bruno.id}", json={"ativo": False})
    assert _login(c, "bruno", "senha-bruno").status_code == 403
    c.put("/api/config/ldap", json={**c.get("/api/config/ldap").json(), "ativo": False})
    crud.atualizar_usuario(db, bruno.id, ativo=True)
    assert _login(c, "bruno", "senha-bruno").status_code == 400  # directory off: no login for LDAP users


def test_conta_local_tem_prioridade_e_diretorio_fora_do_ar(ldap_ligado):
    c, db, estado = ldap_ligado
    from app import main
    crud.criar_usuario(db, "ldap-local", main.pwd_context.hash("senha-local-1"), papel="visualizador")
    assert _login(c, "ldap-local", "senha-diretorio").status_code == 400  # never taken over by the directory
    assert _login(c, "ldap-local", "senha-local-1").status_code == 200
    assert crud.get_usuario(db, "ldap-local").origem == "local"

    estado["fora"] = True
    assert _login(c, "ana", "senha-ana").status_code == 503
    assert _login(c, "ldap-local", "senha-local-1").status_code == 200  # local accounts keep working
    assert c.post("/api/config/ldap/teste", json={"usuario": "ana"}).status_code == 400
    estado["fora"] = False

    r = c.post("/api/config/ldap/teste", json={"usuario": "ana"}).json()
    assert r["encontrado"] and r["papel"] == "admin" and r["grupos"] == [ADMINS] and r["dn"].startswith("cn=Ana Souza")
    assert c.post("/api/config/ldap/teste", json={"usuario": "ana", "senha": "errada"}).json() == {"encontrado": False, "senha_ok": False}
    assert c.post("/api/config/ldap/teste", json={"usuario": "ana", "senha": "senha-ana"}).json()["senha_ok"]
    assert c.post("/api/config/ldap/teste", json={"usuario": "ninguem"}).json() == {"encontrado": False}
    assert crud.get_usuario(db, "ana") is None  # testing does not create the user


def test_2fa_de_usuario_ldap_confere_a_senha_no_diretorio(ldap_ligado):
    c, db, _ = ldap_ligado
    token = _login(c, "ana", "senha-ana").json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert c.post("/api/me/2fa/iniciar", json={"senha": "errada"}, headers=h).status_code == 400
    assert c.post("/api/me/2fa/iniciar", json={"senha": "senha-ana"}, headers=h).status_code == 200


def test_filtro_escapa_o_nome_digitado(ldap_ligado):
    c, db, _ = ldap_ligado
    # "*" would match every account if it went into the filter as is
    assert _login(c, "*", "senha-ana").status_code == 400
    assert _login(c, "an*", "senha-ana").status_code == 400
    cfg = ldap_auth.ler_config(db)
    assert ldap_auth.papel_dos_grupos(cfg, ["CN=NetCable-Admins, OU=Grupos, DC=empresa, DC=local"]) == "admin"
