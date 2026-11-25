import pytest

from app import models, totp


def test_totp_vetores_da_rfc_6238():
    # RFC 6238 appendix B (SHA-1), last 6 of the 8 digits.
    segredo = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32 of "12345678901234567890"
    assert totp.codigo(segredo, 59 // 30) == "287082"
    assert totp.codigo(segredo, 1111111109 // 30) == "081804"
    assert totp.codigo(segredo, 1234567890 // 30) == "005924"


def test_totp_janela_e_reuso():
    segredo = totp.novo_segredo()
    agora = 1_700_000_000
    passo = totp.passo_atual(agora)
    assert totp.verificar(segredo, totp.codigo(segredo, passo), agora=agora) == passo
    assert totp.verificar(segredo, totp.codigo(segredo, passo - 1), agora=agora) == passo - 1  # phone clock behind
    assert totp.verificar(segredo, totp.codigo(segredo, passo - 3), agora=agora) is None
    assert totp.verificar(segredo, totp.codigo(segredo, passo), ultimo_passo=passo, agora=agora) is None  # used once
    assert totp.verificar(segredo, "12345", agora=agora) is None
    assert totp.verificar(segredo, " " + totp.codigo(segredo, passo)[:3] + " " + totp.codigo(segredo, passo)[3:], agora=agora) == passo


def test_codigos_de_recuperacao_valem_uma_vez():
    codigos, guardados = totp.novos_codigos_recuperacao()
    assert len(codigos) == 10 and len(set(codigos)) == 10 and codigos[0] not in guardados
    ok, guardados = totp.usar_codigo_recuperacao(guardados, codigos[3].upper().replace("-", " "))
    assert ok and totp.restantes(guardados) == 9
    ok, guardados = totp.usar_codigo_recuperacao(guardados, codigos[3])
    assert not ok


def _codigo_atual(db, username):
    from app import main
    u = db.query(models.Usuario).filter(models.Usuario.username == username).one()
    db.refresh(u)
    return totp.codigo(main.abrir_config(u.totp_segredo)["s"], totp.passo_atual())


@pytest.fixture()
def sem_bloqueio():
    from app import main
    main.login_failures.clear()
    yield
    main.login_failures.clear()


def test_fluxo_completo_de_2fa(cliente, sem_bloqueio):
    c, db = cliente
    assert c.post("/api/me/2fa/iniciar", json={"senha": "errada"}).status_code == 400
    r = c.post("/api/me/2fa/iniciar", json={"senha": "senha-forte-1"}).json()
    assert r["uri"].startswith("otpauth://totp/NetCable:backup-admin?secret=" + r["segredo"])
    # Not enforced until confirmed with a code
    assert "access_token" in c.post("/api/login", data={"username": "backup-admin", "password": "senha-forte-1"}).json()
    assert c.post("/api/me/2fa/ativar", json={"codigo": "000000"}).status_code == 400
    ativado = c.post("/api/me/2fa/ativar", json={"codigo": _codigo_atual(db, "backup-admin")}).json()
    recuperacao = ativado["codigos_recuperacao"]
    assert len(recuperacao) == 10
    me = c.get("/api/me").json()
    assert me["totp_ativo"] and me["totp_recuperacao_restantes"] == 10

    # The secret is stored encrypted
    u = db.query(models.Usuario).filter(models.Usuario.username == "backup-admin").one()
    db.refresh(u)
    assert u.totp_segredo.startswith("gAAAA") and r["segredo"] not in u.totp_segredo

    # Login now needs the code; the half-done token is not a session
    etapa = c.post("/api/login", data={"username": "backup-admin", "password": "senha-forte-1"}).json()
    assert etapa["requer_2fa"] and "access_token" not in etapa
    assert c.get("/api/me", headers={"Authorization": f"Bearer {etapa['desafio']}"}).status_code == 401
    assert c.post("/api/login/2fa", json={"desafio": etapa["desafio"], "codigo": "000000"}).status_code == 400
    assert c.post("/api/login/2fa", json={"desafio": "lixo", "codigo": "000000"}).status_code == 401

    # The code used to activate cannot be replayed; the next one (inside the clock-drift window) works
    from app import main
    segredo, usado = main.abrir_config(u.totp_segredo)["s"], u.totp_ultimo_passo
    assert c.post("/api/login/2fa", json={"desafio": etapa["desafio"], "codigo": totp.codigo(segredo, usado)}).status_code == 400
    ok = c.post("/api/login/2fa", json={"desafio": etapa["desafio"], "codigo": totp.codigo(segredo, usado + 1)}).json()
    token = ok["access_token"]
    assert c.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    # Recovery code works once
    etapa = c.post("/api/login", data={"username": "backup-admin", "password": "senha-forte-1"}).json()
    r = c.post("/api/login/2fa", json={"desafio": etapa["desafio"], "codigo": recuperacao[0]}).json()
    assert "access_token" in r and r["recuperacao_restantes"] == 9
    assert c.post("/api/login/2fa", json={"desafio": etapa["desafio"], "codigo": recuperacao[0]}).status_code == 400

    # Turning it off needs the password and a code
    assert c.post("/api/me/2fa/desativar", json={"codigo": recuperacao[1]}).status_code == 400
    assert c.post("/api/me/2fa/desativar", json={"senha": "senha-forte-1", "codigo": recuperacao[1]}).status_code == 200
    assert not c.get("/api/me").json()["totp_ativo"]
    acoes = {a.acao for a in db.query(models.Auditoria).all()}
    assert {"2fa.ativado", "2fa.desativado", "login.2fa_falhou"} <= acoes
    db.query(models.Auditoria).delete()
    db.commit()


def test_codigos_errados_bloqueiam_mesmo_com_a_senha_certa(cliente, sem_bloqueio):
    c, db = cliente
    from app import main
    c.post("/api/me/2fa/iniciar", json={"senha": "senha-forte-1"})
    c.post("/api/me/2fa/ativar", json={"codigo": _codigo_atual(db, "backup-admin")})
    for _ in range(main.LOGIN_MAX_FAILURES):
        # Logging in with the password again must not reset the counter of wrong codes
        etapa = c.post("/api/login", data={"username": "backup-admin", "password": "senha-forte-1"}).json()
        assert c.post("/api/login/2fa", json={"desafio": etapa["desafio"], "codigo": "000000"}).status_code == 400
    assert c.post("/api/login", data={"username": "backup-admin", "password": "senha-forte-1"}).status_code == 429


def test_admin_remove_2fa_e_comando_de_recuperacao(cliente, sem_bloqueio):
    c, db = cliente
    from app import main, crud, redefinir_2fa
    u = crud.criar_usuario(db, "dois-fatores", main.pwd_context.hash("senha-forte-1"), papel="editor")
    try:
        outro = {"Authorization": f"Bearer {main.criar_token({'sub': 'dois-fatores'})}"}
        c.post("/api/me/2fa/iniciar", json={"senha": "senha-forte-1"}, headers=outro)
        c.post("/api/me/2fa/ativar", json={"codigo": _codigo_atual(db, "dois-fatores")}, headers=outro)
        lista = {x["username"]: x for x in c.get("/api/usuarios").json()}
        assert lista["dois-fatores"]["totp_ativo"]
        # Editors cannot remove someone's 2FA
        assert c.put(f"/api/usuarios/{u.id}", json={"remover_2fa": True}, headers=outro).status_code == 403
        assert c.put(f"/api/usuarios/{u.id}", json={"remover_2fa": True}).json()["totp_ativo"] is False
        assert "access_token" in c.post("/api/login", data={"username": "dois-fatores", "password": "senha-forte-1"}).json()

        c.post("/api/me/2fa/iniciar", json={"senha": "senha-forte-1"}, headers=outro)
        c.post("/api/me/2fa/ativar", json={"codigo": _codigo_atual(db, "dois-fatores")}, headers=outro)
        assert redefinir_2fa.main(["dois-fatores"]) == 0
        assert redefinir_2fa.main(["nao-existe"]) == 1
        db.expire_all()
        assert not db.get(models.Usuario, u.id).totp_ativo
    finally:
        db.query(models.Auditoria).delete()
        db.delete(db.get(models.Usuario, u.id))
        db.commit()
