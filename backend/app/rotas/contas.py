"""First-run setup, login (with two-factor authentication), own profile and team users."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import jwt
from jwt import PyJWTError as JWTError
import time
import os
import threading
from collections import defaultdict
from pydantic import BaseModel
from typing import Optional
from .. import models, crud
from ..i18n import IDIOMAS
from ..database import SessionLocal
from .. import auditoria, totp
from ..nucleo import (
    ALGORITHM,
    HORARIO_RE,
    SECRET_KEY,
    USERNAME_RE,
    VERSAO,
    abrir_config,
    criar_token,
    get_current_user,
    get_db,
    logger,
    proteger_config,
    pwd_context,
    requer_admin,
    verificar_senha,
)
from ..monitoramento import enviar_relatorio
from fastapi import APIRouter

router = APIRouter()


# --- USUÁRIO ADMIN INICIAL ---
# Com ADMIN_PASSWORD definido, o usuário ADMIN_USER é criado/garantido como admin ativo
# (útil para automação e para recuperar o acesso). Sem ele, a primeira pessoa que abrir
# o NetCable cria a conta de administrador pelo assistente de primeiro acesso.
ADMIN_USER = os.getenv("ADMIN_USER", "admin").strip() or "admin"


ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or None


if ADMIN_PASSWORD:
    db_init = SessionLocal()
    admin_user = crud.get_usuario(db_init, ADMIN_USER)
    if not admin_user:
        crud.criar_usuario(db_init, ADMIN_USER, pwd_context.hash(ADMIN_PASSWORD), None, papel="admin")
    elif admin_user.papel != "admin" or not admin_user.ativo:
        crud.atualizar_usuario(db_init, admin_user.id, papel="admin", ativo=True)
    db_init.close()


_trava_setup = threading.Lock()


def precisa_de_setup(db: Session):
    return db.query(models.Usuario).count() == 0


class SetupIn(BaseModel):
    username: str
    senha: str
    email: Optional[str] = None
    idioma: Optional[str] = None


@router.get("/api/setup")
def status_setup(db: Session = Depends(get_db)):
    return {"necessario": precisa_de_setup(db), "versao": VERSAO}


@router.post("/api/setup")
def concluir_setup(dados: SetupIn, request: Request, db: Session = Depends(get_db)):
    """Cria a primeira conta (admin). Só funciona enquanto não existir nenhum usuário."""
    with _trava_setup:
        if not precisa_de_setup(db):
            raise HTTPException(status_code=409, detail="O NetCable já foi configurado.")
        username = dados.username.strip()
        if not USERNAME_RE.match(username):
            raise HTTPException(status_code=400, detail="Usuário inválido: use de 3 a 50 letras, números ou . _ @ -")
        if len(dados.senha) < 8:
            raise HTTPException(status_code=400, detail="A senha precisa ter pelo menos 8 caracteres.")
        admin = crud.criar_usuario(db, username, pwd_context.hash(dados.senha), (dados.email or "").strip() or None, papel="admin")
        if dados.idioma in IDIOMAS:
            crud.atualizar_usuario(db, admin.id, idioma=dados.idioma)
    logger.info("Primeiro acesso concluído: administrador '%s' criado", username)
    auditoria.registrar(db, username, "setup.admin_criado", request=request)
    return {"access_token": criar_token(data={"sub": username}), "token_type": "bearer"}


login_failures = defaultdict(list)


LOGIN_WINDOW_SECONDS = 300


LOGIN_MAX_FAILURES = 5


@router.post("/api/login")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    now = time.monotonic()
    failures = [timestamp for timestamp in login_failures[form_data.username] if now - timestamp < LOGIN_WINDOW_SECONDS]
    login_failures[form_data.username] = failures
    if len(failures) >= LOGIN_MAX_FAILURES:
        auditoria.registrar(db, form_data.username[:80], "login.bloqueado", request=request)
        raise HTTPException(status_code=429, detail="Muitas tentativas. Tente novamente em alguns minutos.")
    user = crud.get_usuario(db, form_data.username)
    if not user or not verificar_senha(form_data.password, user.password_hash):
        login_failures[form_data.username].append(now)
        auditoria.registrar(db, form_data.username[:80], "login.falhou", request=request)
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos")
    if not user.ativo:
        auditoria.registrar(db, user, "login.desativado", request=request)
        raise HTTPException(status_code=403, detail="Usuário desativado. Fale com um administrador.")
    if user.totp_ativo:
        # Password ok; the failure counter is only cleared after the code, so it also limits code guessing.
        desafio = jwt.encode({"sub": user.username, "fase": "2fa", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                             SECRET_KEY, algorithm=ALGORITHM)
        return {"requer_2fa": True, "desafio": desafio}
    login_failures.pop(form_data.username, None)
    auditoria.registrar(db, user, "login.ok", request=request)
    access_token = criar_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


class Login2faIn(BaseModel):
    desafio: str
    codigo: str


def _conferir_segundo_fator(db: Session, user: models.Usuario, codigo: str):
    """Checks a TOTP code or a recovery code. Returns "totp", "recuperacao" or None (and saves what changed)."""
    segredo = abrir_config(user.totp_segredo).get("s")
    passo = totp.verificar(segredo, codigo, user.totp_ultimo_passo)
    if passo is not None:
        user.totp_ultimo_passo = passo
        db.commit()
        return "totp"
    ok, restantes = totp.usar_codigo_recuperacao(user.totp_recuperacao, codigo)
    if ok:
        user.totp_recuperacao = restantes
        db.commit()
        return "recuperacao"
    return None


@router.post("/api/login/2fa")
def login_2fa(dados: Login2faIn, request: Request, db: Session = Depends(get_db)):
    expirou = HTTPException(status_code=401, detail="O login expirou. Digite a senha de novo.")
    try:
        payload = jwt.decode(dados.desafio, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise expirou
    username = payload.get("sub") or ""
    if payload.get("fase") != "2fa":
        raise expirou
    now = time.monotonic()
    failures = [momento for momento in login_failures[username] if now - momento < LOGIN_WINDOW_SECONDS]
    login_failures[username] = failures
    if len(failures) >= LOGIN_MAX_FAILURES:
        auditoria.registrar(db, username[:80], "login.bloqueado", request=request)
        raise HTTPException(status_code=429, detail="Muitas tentativas. Tente novamente em alguns minutos.")
    user = crud.get_usuario(db, username)
    if not user or not user.ativo or not user.totp_ativo:
        raise expirou
    metodo = _conferir_segundo_fator(db, user, dados.codigo)
    if not metodo:
        login_failures[username].append(now)
        auditoria.registrar(db, user, "login.2fa_falhou", request=request)
        raise HTTPException(status_code=400, detail="Código de verificação incorreto.")
    login_failures.pop(username, None)
    auditoria.registrar(db, user, "login.ok", "recovery code" if metodo == "recuperacao" else "2FA", request)
    resposta = {"access_token": criar_token(data={"sub": user.username}), "token_type": "bearer"}
    if metodo == "recuperacao":
        resposta["recuperacao_restantes"] = totp.restantes(user.totp_recuperacao)
    return resposta


def usuario_publico(u: models.Usuario):
    return {
        "id": u.id, "username": u.username, "email": u.email, "papel": u.papel, "ativo": u.ativo,
        "receber_alertas": u.receber_alertas, "relatorio_diario": u.relatorio_diario,
        "relatorio_horario": u.relatorio_horario, "idioma": u.idioma or "en", "totp_ativo": bool(u.totp_ativo),
    }


@router.get("/api/me")
def read_users_me(current_user: models.Usuario = Depends(get_current_user)):
    dados = usuario_publico(current_user)
    if current_user.totp_ativo:
        dados["totp_recuperacao_restantes"] = totp.restantes(current_user.totp_recuperacao)
    return dados


# --- VERIFICAÇÃO EM DUAS ETAPAS (2FA) ---
class Iniciar2faIn(BaseModel):
    senha: str


class Codigo2faIn(BaseModel):
    codigo: str
    senha: Optional[str] = None


@router.post("/api/me/2fa/iniciar")
def iniciar_2fa(dados: Iniciar2faIn, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Step 1: new secret (shown as a QR code). 2FA is only enforced after /ativar with a valid code."""
    if user.totp_ativo:
        raise HTTPException(status_code=400, detail="A verificação em duas etapas já está ativa.")
    if not verificar_senha(dados.senha, user.password_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    segredo = totp.novo_segredo()
    user.totp_segredo = proteger_config({"s": segredo})
    user.totp_ultimo_passo = None
    db.commit()
    return {"segredo": segredo, "uri": totp.uri(segredo, user.username)}


@router.post("/api/me/2fa/ativar")
def ativar_2fa(dados: Codigo2faIn, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    if user.totp_ativo:
        raise HTTPException(status_code=400, detail="A verificação em duas etapas já está ativa.")
    segredo = abrir_config(user.totp_segredo).get("s")
    if not segredo:
        raise HTTPException(status_code=400, detail="Comece a configuração de novo.")
    passo = totp.verificar(segredo, dados.codigo)
    if passo is None:
        raise HTTPException(status_code=400, detail="Código incorreto. Confira o horário do celular e tente o código atual.")
    codigos, hashes = totp.novos_codigos_recuperacao()
    user.totp_ativo, user.totp_ultimo_passo, user.totp_recuperacao = True, passo, hashes
    db.commit()
    auditoria.registrar(db, user, "2fa.ativado", request=request)
    return {"codigos_recuperacao": codigos}


@router.post("/api/me/2fa/desativar")
def desativar_2fa(dados: Codigo2faIn, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    if not user.totp_ativo:
        return {"status": "ok"}
    if not dados.senha or not verificar_senha(dados.senha, user.password_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    if not _conferir_segundo_fator(db, user, dados.codigo):
        raise HTTPException(status_code=400, detail="Código de verificação incorreto.")
    _limpar_2fa(db, user)
    auditoria.registrar(db, user, "2fa.desativado", request=request)
    return {"status": "ok"}


@router.post("/api/me/2fa/recuperacao")
def novos_codigos_recuperacao(dados: Codigo2faIn, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    if not user.totp_ativo:
        raise HTTPException(status_code=400, detail="A verificação em duas etapas não está ativa.")
    if _conferir_segundo_fator(db, user, dados.codigo) != "totp":
        raise HTTPException(status_code=400, detail="Código de verificação incorreto.")
    codigos, hashes = totp.novos_codigos_recuperacao()
    user.totp_recuperacao = hashes
    db.commit()
    auditoria.registrar(db, user, "2fa.recuperacao_gerada", request=request)
    return {"codigos_recuperacao": codigos}


def _limpar_2fa(db: Session, user: models.Usuario):
    user.totp_ativo, user.totp_segredo, user.totp_ultimo_passo, user.totp_recuperacao = False, None, None, None
    db.commit()


class PerfilUpdate(BaseModel):
    email: Optional[str] = None
    senha_atual: Optional[str] = None
    nova_senha: Optional[str] = None
    receber_alertas: Optional[bool] = None
    relatorio_diario: Optional[bool] = None
    relatorio_horario: Optional[str] = None
    idioma: Optional[str] = None


@router.put("/api/me/perfil")
def atualizar_perfil_usuario(dados: PerfilUpdate, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    nova_hash = None
    if dados.nova_senha:
        if len(dados.nova_senha) < 8:
            raise HTTPException(status_code=400, detail="A nova senha precisa ter pelo menos 8 caracteres.")
        if not dados.senha_atual or not verificar_senha(dados.senha_atual, user.password_hash):
            raise HTTPException(status_code=400, detail="Senha atual incorreta.")
        nova_hash = pwd_context.hash(dados.nova_senha)
    if dados.relatorio_horario is not None and not HORARIO_RE.match(dados.relatorio_horario):
        raise HTTPException(status_code=400, detail="Horário do relatório inválido (use HH:MM).")
    if dados.idioma is not None and dados.idioma not in IDIOMAS:
        raise HTTPException(status_code=400, detail="Idioma inválido (use en ou pt).")
    email = dados.email.strip() if dados.email is not None else None
    if (dados.receber_alertas or dados.relatorio_diario) and not (email if email is not None else user.email):
        raise HTTPException(status_code=400, detail="Informe um e-mail para receber alertas e relatórios.")
    atualizado = crud.atualizar_usuario(
        db, user.id, email=email, password_hash=nova_hash,
        receber_alertas=dados.receber_alertas, relatorio_diario=dados.relatorio_diario,
        relatorio_horario=dados.relatorio_horario, idioma=dados.idioma,
    )
    if nova_hash:
        auditoria.registrar(db, user, "perfil.senha_alterada", request=request)
    return usuario_publico(atualizado)


@router.post("/api/me/relatorio/enviar")
def enviar_meu_relatorio(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Envia agora o relatório das últimas 24h para o e-mail do usuário (útil para testar)."""
    if not user.email:
        raise HTTPException(status_code=400, detail="Cadastre um e-mail no seu perfil primeiro.")
    try:
        enviar_relatorio(db, [user.email], idioma=user.idioma)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha ao enviar o relatório: {exc}")
    return {"status": "enviado", "para": user.email}


# --- GERENCIAMENTO DE USUÁRIOS (ADMIN) ---
class UsuarioCreate(BaseModel):
    username: str
    senha: str
    email: Optional[str] = None
    papel: str = "editor"


class UsuarioUpdate(BaseModel):
    email: Optional[str] = None
    papel: Optional[str] = None
    ativo: Optional[bool] = None
    nova_senha: Optional[str] = None
    remover_2fa: Optional[bool] = None  # admin: the user lost the phone and the recovery codes


@router.get("/api/usuarios")
def listar_usuarios(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    return [usuario_publico(u) for u in crud.listar_usuarios(db)]


@router.post("/api/usuarios")
def criar_usuario_rota(dados: UsuarioCreate, request: Request, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    username = dados.username.strip()
    if not USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="Usuário inválido: use de 3 a 50 letras, números ou . _ @ -")
    if dados.papel not in models.PAPEIS:
        raise HTTPException(status_code=400, detail="Papel inválido.")
    if len(dados.senha) < 8:
        raise HTTPException(status_code=400, detail="A senha precisa ter pelo menos 8 caracteres.")
    if crud.get_usuario(db, username):
        raise HTTPException(status_code=400, detail="Já existe um usuário com esse nome.")
    novo = crud.criar_usuario(db, username, pwd_context.hash(dados.senha), (dados.email or "").strip() or None, dados.papel)
    auditoria.registrar(db, admin, "usuario.criado", f"{username} ({dados.papel})", request)
    return usuario_publico(novo)


@router.put("/api/usuarios/{user_id}")
def atualizar_usuario_rota(user_id: int, dados: UsuarioUpdate, request: Request, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    alvo = crud.get_usuario_por_id(db, user_id)
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if dados.papel is not None and dados.papel not in models.PAPEIS:
        raise HTTPException(status_code=400, detail="Papel inválido.")
    perde_admin = alvo.papel == "admin" and alvo.ativo and ((dados.papel and dados.papel != "admin") or dados.ativo is False)
    if perde_admin and crud.contar_admins_ativos(db, exceto_id=alvo.id) == 0:
        raise HTTPException(status_code=400, detail="O sistema precisa de pelo menos um administrador ativo.")
    nova_hash = None
    if dados.nova_senha:
        if len(dados.nova_senha) < 8:
            raise HTTPException(status_code=400, detail="A senha precisa ter pelo menos 8 caracteres.")
        nova_hash = pwd_context.hash(dados.nova_senha)
    email = dados.email.strip() if dados.email is not None else None
    mudancas = []
    if dados.papel is not None and dados.papel != alvo.papel:
        mudancas.append(f"{alvo.papel} -> {dados.papel}")
    if dados.ativo is not None and dados.ativo != alvo.ativo:
        mudancas.append("active" if dados.ativo else "disabled")
    if nova_hash:
        mudancas.append("password reset")
    if email is not None and email != (alvo.email or ""):
        mudancas.append("email")
    if dados.remover_2fa and alvo.totp_ativo:
        _limpar_2fa(db, alvo)
        mudancas.append("2FA removed")
    atualizado = crud.atualizar_usuario(db, user_id, email=email, papel=dados.papel, ativo=dados.ativo, password_hash=nova_hash)
    if mudancas:
        auditoria.registrar(db, admin, "usuario.alterado", f"{atualizado.username}: {', '.join(mudancas)}", request)
    return usuario_publico(atualizado)


@router.delete("/api/usuarios/{user_id}")
def deletar_usuario_rota(user_id: int, request: Request, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir o seu próprio usuário.")
    alvo = crud.get_usuario_por_id(db, user_id)
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if alvo.papel == "admin" and crud.contar_admins_ativos(db, exceto_id=alvo.id) == 0:
        raise HTTPException(status_code=400, detail="O sistema precisa de pelo menos um administrador ativo.")
    nome = alvo.username
    crud.deletar_usuario(db, user_id)
    auditoria.registrar(db, admin, "usuario.excluido", nome, request)
    return {"status": "sucesso"}
