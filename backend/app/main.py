from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
import ping3
import socket
import time
import os
import re
import json
import base64
import hashlib
import logging
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel
from typing import List, Optional
from zoneinfo import ZoneInfo
from .snmp_service import test as snmp_test, discover_neighbors, SNMPUnavailableError

from . import models, crud, alerts, email_service
from .i18n import traduzir, idioma_do_cabecalho, normalizar, IDIOMAS
from .database import engine, SessionLocal, DATA_DIR, DB_PATH
from . import migracoes, backup, regras_alerta, descoberta, snmp_service, metricas_snmp
from fastapi import UploadFile, File
from fastapi.responses import FileResponse
import zipfile

models.Base.metadata.create_all(bind=engine)

# Atualiza bancos de versões anteriores (com cópia de segurança antes de migrar).
migracoes.aplicar(engine, DB_PATH)

def _versao():
    """APP_VERSION (definida no build da imagem) ou o arquivo VERSION do repositório."""
    if os.getenv("APP_VERSION"):
        return os.getenv("APP_VERSION")
    for caminho in (os.path.join(os.path.dirname(__file__), "..", "VERSION"), os.path.join(os.path.dirname(__file__), "..", "..", "VERSION")):
        if os.path.isfile(caminho):
            return open(caminho, encoding="utf-8").read().strip() + "-dev"
    return "dev"


app = FastAPI(title="NetCable API", version=_versao())

ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["http://localhost", "http://localhost:3080", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def erro_traduzido(request: Request, exc: StarletteHTTPException):
    """Devolve a mensagem de erro no idioma da interface (cabeçalho Accept-Language)."""
    idioma = idioma_do_cabecalho(request.headers.get("accept-language"))
    return JSONResponse({"detail": traduzir(exc.detail, idioma)}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response

CHAVE_DEV = "dev-only-change-this-secret"  # usada por versões antigas quando SECRET_KEY não era definida


def carregar_chave_secreta():
    """SECRET_KEY do ambiente; senão, a chave guardada em <dados>/secret.key (criada na 1ª execução).
    Retorna (chave, criada_agora)."""
    do_ambiente = os.getenv("SECRET_KEY", "").strip()
    if do_ambiente:
        return do_ambiente, False
    arquivo = os.path.join(DATA_DIR, "secret.key")
    if os.path.exists(arquivo):
        with open(arquivo, encoding="utf-8") as f:
            return f.read().strip(), False
    nova = secrets.token_urlsafe(48)
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(nova)
    try:
        os.chmod(arquivo, 0o600)
    except OSError:
        pass
    return nova, True


SECRET_KEY, CHAVE_CRIADA_AGORA = carregar_chave_secreta()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("netcable")
# Intervalo (s) do monitoramento em segundo plano no backend. 0 desativa.
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "15"))
MONITOR_WORKERS = int(os.getenv("MONITOR_WORKERS", "16"))
# Falhas seguidas antes de marcar um equipamento online como offline (evita alarme falso).
MONITOR_FAILURE_THRESHOLD = max(1, int(os.getenv("MONITOR_FAILURE_THRESHOLD", "2")))
# Dias de histórico mantidos no banco. 0 mantém para sempre.
HISTORY_RETENTION_DAYS = int(os.getenv("HISTORY_RETENTION_DAYS", "30"))
# Fuso padrão para o horário dos relatórios (pode ser alterado pelo admin na interface).
FUSO_PADRAO = os.getenv("TZ", "America/Sao_Paulo")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7


def iso_utc(momento):
    """Datas do banco são UTC sem fuso; o sufixo Z evita que o navegador as leia como hora local."""
    return momento.isoformat() + "Z" if momento else None


def _fernet_de(chave):
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(chave.encode()).digest()))


fernet = _fernet_de(SECRET_KEY)


def _recifrar_segredos_antigos():
    """Instalações antigas cifravam senhas (SNMP/SMTP) com a chave de desenvolvimento.
    Ao gerar a chave nova, re-cifra o que ainda estiver na chave antiga para não perder nada."""
    antiga = _fernet_de(CHAVE_DEV)
    total = 0
    with engine.begin() as conexao:
        for tabela, chave_col, valor_col in (("equipamentos", "id", "monitor_config"), ("configuracoes", "chave", "valor")):
            for ident, valor in conexao.exec_driver_sql(f"SELECT {chave_col}, {valor_col} FROM {tabela} WHERE {valor_col} IS NOT NULL").fetchall():
                try:
                    claro = antiga.decrypt(valor.encode())
                except (InvalidToken, ValueError, TypeError, AttributeError):
                    continue
                conexao.exec_driver_sql(f"UPDATE {tabela} SET {valor_col} = ? WHERE {chave_col} = ?", (fernet.encrypt(claro).decode(), ident))
                total += 1
    return total


if CHAVE_CRIADA_AGORA:
    recifrados = _recifrar_segredos_antigos()
    logging.getLogger("netcable").info("Chave secreta gerada em %s (%s segredo(s) re-cifrado(s))", os.path.join(DATA_DIR, "secret.key"), recifrados)


def proteger_config(config):
    if not config:
        return None
    return fernet.encrypt(json.dumps(config).encode()).decode()


def abrir_config(value):
    if not value:
        return {}
    try:
        return json.loads(fernet.decrypt(value.encode()).decode())
    except (InvalidToken, ValueError, TypeError):
        return {}


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- CONFIGURAÇÕES DO SISTEMA (SMTP / fuso) ---
def get_smtp_config(db: Session):
    cfg = crud.get_configuracoes(db, "smtp.")
    smtp = {chave[len("smtp."):]: valor for chave, valor in cfg.items()}
    smtp["senha"] = abrir_config(smtp.get("senha")).get("senha", "") if smtp.get("senha") else ""
    return smtp


def get_fuso(db: Session):
    nome = crud.get_configuracoes(db, "sistema.fuso").get("sistema.fuso") or FUSO_PADRAO
    try:
        return ZoneInfo(nome)
    except Exception:
        logger.warning("Fuso horário inválido '%s'; usando UTC.", nome)
        return timezone.utc


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    database_ok = False
    database_error = None
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    except Exception as exc:
        database_error = str(exc)
    try:
        from .snmp_service import _hlapi
        _hlapi()
        snmp = {"installed": True, "status": "ready"}
    except Exception as exc:
        snmp = {"installed": False, "status": "unavailable", "detail": str(exc)}
    return {
        "status": "ok" if database_ok else "degraded",
        "api": "online",
        "version": app.version,
        "database": {"connected": database_ok, "error": database_error},
        "snmp": snmp,
        "database_path": str(engine.url.database),
        "monitor": {
            "enabled": MONITOR_INTERVAL > 0,
            "interval": MONITOR_INTERVAL,
            "failure_threshold": MONITOR_FAILURE_THRESHOLD,
            "last_cycle": iso_utc(_ultimo_ciclo["fim"]),
            "last_cycle_seconds": _ultimo_ciclo["duracao"],
            "equipments": _ultimo_ciclo["equipamentos"],
        },
        "alerts": alerts.canais_configurados(get_smtp_config(db), get_canais_config(db)) if database_ok else {},
        "history_retention_days": HISTORY_RETENTION_DAYS,
        "security": {
            "secret_key_configured": SECRET_KEY != CHAVE_DEV,
            "default_admin_password": (ADMIN_PASSWORD or "") in {"admin", "altere_esta_senha"},
        },
    }


# --- AUTENTICAÇÃO E PAPÉIS ---
def verificar_senha(senha_plana, senha_hash):
    return pwd_context.verify(senha_plana, senha_hash)


def criar_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Credenciais inválidas")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_usuario(db, username=username)
    if user is None or not user.ativo:
        raise credentials_exception
    return user


def requer_editor(user: models.Usuario = Depends(get_current_user)):
    if user.papel not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Seu usuário tem acesso somente de visualização.")
    return user


def requer_admin(user: models.Usuario = Depends(get_current_user)):
    if user.papel != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores podem fazer isso.")
    return user


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

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{3,50}$")
_trava_setup = threading.Lock()


def precisa_de_setup(db: Session):
    return db.query(models.Usuario).count() == 0


class SetupIn(BaseModel):
    username: str
    senha: str
    email: Optional[str] = None
    idioma: Optional[str] = None


@app.get("/api/setup")
def status_setup(db: Session = Depends(get_db)):
    return {"necessario": precisa_de_setup(db), "versao": app.version}


@app.post("/api/setup")
def concluir_setup(dados: SetupIn, db: Session = Depends(get_db)):
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
    return {"access_token": criar_token(data={"sub": username}), "token_type": "bearer"}


login_failures = defaultdict(list)
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_FAILURES = 5


@app.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    now = time.monotonic()
    failures = [timestamp for timestamp in login_failures[form_data.username] if now - timestamp < LOGIN_WINDOW_SECONDS]
    login_failures[form_data.username] = failures
    if len(failures) >= LOGIN_MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Tente novamente em alguns minutos.")
    user = crud.get_usuario(db, form_data.username)
    if not user or not verificar_senha(form_data.password, user.password_hash):
        login_failures[form_data.username].append(now)
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos")
    if not user.ativo:
        raise HTTPException(status_code=403, detail="Usuário desativado. Fale com um administrador.")
    login_failures.pop(form_data.username, None)
    access_token = criar_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


def usuario_publico(u: models.Usuario):
    return {
        "id": u.id, "username": u.username, "email": u.email, "papel": u.papel, "ativo": u.ativo,
        "receber_alertas": u.receber_alertas, "relatorio_diario": u.relatorio_diario,
        "relatorio_horario": u.relatorio_horario, "idioma": u.idioma or "en",
    }


@app.get("/api/me")
def read_users_me(current_user: models.Usuario = Depends(get_current_user)):
    return usuario_publico(current_user)


HORARIO_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class PerfilUpdate(BaseModel):
    email: Optional[str] = None
    senha_atual: Optional[str] = None
    nova_senha: Optional[str] = None
    receber_alertas: Optional[bool] = None
    relatorio_diario: Optional[bool] = None
    relatorio_horario: Optional[str] = None
    idioma: Optional[str] = None


@app.put("/api/me/perfil")
def atualizar_perfil_usuario(dados: PerfilUpdate, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
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
    return usuario_publico(atualizado)


@app.post("/api/me/relatorio/enviar")
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


@app.get("/api/usuarios")
def listar_usuarios(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    return [usuario_publico(u) for u in crud.listar_usuarios(db)]


@app.post("/api/usuarios")
def criar_usuario_rota(dados: UsuarioCreate, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
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
    return usuario_publico(novo)


@app.put("/api/usuarios/{user_id}")
def atualizar_usuario_rota(user_id: int, dados: UsuarioUpdate, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
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
    atualizado = crud.atualizar_usuario(db, user_id, email=email, papel=dados.papel, ativo=dados.ativo, password_hash=nova_hash)
    return usuario_publico(atualizado)


@app.delete("/api/usuarios/{user_id}")
def deletar_usuario_rota(user_id: int, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir o seu próprio usuário.")
    alvo = crud.get_usuario_por_id(db, user_id)
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if alvo.papel == "admin" and crud.contar_admins_ativos(db, exceto_id=alvo.id) == 0:
        raise HTTPException(status_code=400, detail="O sistema precisa de pelo menos um administrador ativo.")
    crud.deletar_usuario(db, user_id)
    return {"status": "sucesso"}


# --- CONFIGURAÇÃO DE E-MAIL (ADMIN) ---
class SmtpConfig(BaseModel):
    host: str = ""
    porta: int = 587
    seguranca: str = "starttls"
    usuario: str = ""
    senha: Optional[str] = None  # vazio/None mantém a senha atual
    remetente: str = ""
    fuso: Optional[str] = None


@app.get("/api/config/email")
def obter_config_email(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    smtp = get_smtp_config(db)
    fuso = crud.get_configuracoes(db, "sistema.fuso").get("sistema.fuso") or FUSO_PADRAO
    return {
        "host": smtp.get("host") or "", "porta": int(smtp.get("porta") or 587),
        "seguranca": smtp.get("seguranca") or "starttls", "usuario": smtp.get("usuario") or "",
        "remetente": smtp.get("remetente") or "", "senha_definida": bool(smtp.get("senha")),
        "fuso": fuso, "configurado": email_service.smtp_configurado(smtp),
    }


@app.put("/api/config/email")
def salvar_config_email(dados: SmtpConfig, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    if dados.seguranca not in email_service.SEGURANCAS:
        raise HTTPException(status_code=400, detail="Segurança inválida (use starttls, ssl ou nenhuma).")
    if not 1 <= dados.porta <= 65535:
        raise HTTPException(status_code=400, detail="Porta inválida.")
    if dados.fuso:
        try:
            ZoneInfo(dados.fuso)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Fuso horário desconhecido: {dados.fuso}")
    valores = {
        "smtp.host": dados.host.strip(), "smtp.porta": str(dados.porta), "smtp.seguranca": dados.seguranca,
        "smtp.usuario": dados.usuario.strip(), "smtp.remetente": dados.remetente.strip(),
    }
    if dados.senha:
        valores["smtp.senha"] = proteger_config({"senha": dados.senha})
    if dados.fuso:
        valores["sistema.fuso"] = dados.fuso
    crud.salvar_configuracoes(db, valores)
    return obter_config_email(db, admin)


class EmailTeste(BaseModel):
    destinatario: Optional[str] = None


@app.post("/api/config/email/teste")
def testar_email(dados: EmailTeste, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    destino = (dados.destinatario or admin.email or "").strip()
    if not destino:
        raise HTTPException(status_code=400, detail="Informe um destinatário ou cadastre um e-mail no seu perfil.")
    try:
        email_service.enviar_email(
            get_smtp_config(db), [destino], traduzir("[NetCable] E-mail de teste", admin.idioma),
            traduzir("Se você recebeu esta mensagem, o envio de e-mails do NetCable está funcionando.", admin.idioma),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha no envio: {exc}")
    return {"status": "enviado", "para": destino}


# --- CANAIS DE ALERTA (Telegram, Discord, ntfy, webhook) ---
CAMPOS_CANAIS = ("telegram_token", "telegram_chat", "discord_url", "ntfy_url", "ntfy_token", "webhook_url")
CAMPOS_SECRETOS = ("telegram_token", "discord_url", "ntfy_token", "webhook_url")


def _canais_salvos(db: Session):
    cfg = crud.get_configuracoes(db, "alertas.")
    salvos = {}
    for campo in CAMPOS_CANAIS:
        valor = cfg.get(f"alertas.{campo}") or ""
        if valor and campo in CAMPOS_SECRETOS:
            valor = abrir_config(valor).get("v", "")
        salvos[campo] = valor
    salvos["idioma"] = cfg.get("alertas.idioma") or ""
    return salvos


def get_canais_config(db: Session):
    """Configuração da interface; campos vazios usam as variáveis de ambiente."""
    salvos, ambiente = _canais_salvos(db), alerts.canais_do_ambiente()
    return {campo: salvos.get(campo) or ambiente.get(campo, "") for campo in (*CAMPOS_CANAIS, "idioma")}


class CanaisIn(BaseModel):
    # Campos secretos: None mantém o valor atual; "" apaga.
    telegram_token: Optional[str] = None
    telegram_chat: Optional[str] = None
    discord_url: Optional[str] = None
    ntfy_url: Optional[str] = None
    ntfy_token: Optional[str] = None
    webhook_url: Optional[str] = None
    idioma: Optional[str] = None


@app.get("/api/config/alertas")
def obter_canais(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    salvos, ambiente, efetivo = _canais_salvos(db), alerts.canais_do_ambiente(), get_canais_config(db)
    resposta = {"idioma": efetivo["idioma"] or "en", "ativos": alerts.canais_configurados(None, efetivo)}
    for campo in CAMPOS_CANAIS:
        if campo in CAMPOS_SECRETOS:
            resposta[f"{campo}_definido"] = bool(salvos[campo])
        else:
            resposta[campo] = salvos[campo]
        resposta[f"{campo}_ambiente"] = bool(ambiente.get(campo)) and not salvos[campo]
    return resposta


@app.put("/api/config/alertas")
def salvar_canais(dados: CanaisIn, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    valores = {}
    for campo in CAMPOS_CANAIS:
        valor = getattr(dados, campo)
        if valor is None:
            continue
        valor = valor.strip()
        if campo.endswith("_url") and valor and not re.match(r"^https?://", valor, re.I):
            raise HTTPException(status_code=400, detail="Use um endereço que comece com http:// ou https://.")
        valores[f"alertas.{campo}"] = proteger_config({"v": valor}) if (valor and campo in CAMPOS_SECRETOS) else valor
    if dados.idioma is not None:
        if dados.idioma not in IDIOMAS:
            raise HTTPException(status_code=400, detail="Idioma inválido (use en ou pt).")
        valores["alertas.idioma"] = dados.idioma
    crud.salvar_configuracoes(db, valores)
    return obter_canais(db, admin)


class CanalTeste(BaseModel):
    canal: str


@app.post("/api/config/alertas/teste")
def testar_canal(dados: CanalTeste, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    cfg = get_canais_config(db)
    if not alerts.canais_configurados(None, cfg).get(dados.canal):
        raise HTTPException(status_code=400, detail="Canal não configurado.")
    try:
        alerts.testar_canal(dados.canal, cfg)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha no envio: {alerts.erro_seguro(exc, cfg)}")
    return {"status": "enviado"}


# --- PROJETOS ---
@app.get("/api/projetos")
def listar_projetos(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    return crud.resumo_projetos(db)


@app.post("/api/projetos")
def novo_projeto(nome: str, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.criar_projeto(db, nome, user.id)
    return {"id": projeto.id, "nome": projeto.nome}


@app.put("/api/projetos/{projeto_id}")
def editar_nome_projeto(projeto_id: int, novo_nome: str, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.atualizar_projeto_nome(db, projeto_id, novo_nome)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"id": projeto.id, "nome": projeto.nome}


@app.delete("/api/projetos/{projeto_id}")
def deletar_projeto_rota(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    if crud.deletar_projeto(db, projeto_id):
        return {"status": "sucesso"}
    raise HTTPException(status_code=404, detail="Projeto não encontrado")


# --- EXPORTAR / IMPORTAR MAPAS ---
LIMITE_IMPORTACAO = 50 * 1024 * 1024


@app.get("/api/projetos/{projeto_id}/exportar")
def exportar_projeto_rota(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return backup.exportar_projeto(db, projeto, abrir_config, app.version)


@app.post("/api/projetos/importar")
async def importar_projeto_rota(arquivo: UploadFile = File(...), db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    conteudo = await arquivo.read(LIMITE_IMPORTACAO + 1)
    if len(conteudo) > LIMITE_IMPORTACAO:
        raise HTTPException(status_code=413, detail="Arquivo grande demais.")
    try:
        importados = backup.importar_arquivo(db, conteudo, user.id, proteger_config)
    except (ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile) as exc:
        legivel = isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError)
        detalhe = str(exc) if legivel else "Arquivo de mapa inválido."
        raise HTTPException(status_code=400, detail=detalhe)
    logger.info("%s importou %d mapa(s)", user.username, len(importados))
    return {"importados": importados}


# --- MONITORAMENTO E DESCOBERTA ---
class MonitorRequest(BaseModel):
    equipmentId: Optional[str] = None
    ip: str
    mode: str = "ip"
    config: Optional[dict] = None


def registrar_monitoramento(db: Session, equipamento, resultado):
    """Grava o resultado. Retorna o evento de alerta (dict) se o status mudou e o
    equipamento tem notificação ligada; caso contrário None."""
    if not equipamento:
        return None
    status = resultado.get("status", "offline")
    tempo_ms = resultado.get("tempo_ms")
    crud.atualizar_status_equipamento(db, equipamento.id, status, tempo_ms)
    _, mudou, status_anterior = crud.registrar_status(db, equipamento.id, status, tempo_ms)
    if not mudou:
        return None
    logger.info("Status alterado: %s (%s) %s -> %s", equipamento.nome, equipamento.ip, status_anterior, status)
    if not equipamento.notificar:
        return None
    projeto_nome = equipamento.projeto.nome if equipamento.projeto else None
    return alerts.montar_evento(equipamento, projeto_nome, status, status_anterior, tempo_ms)


def enviar_alertas(db: Session, eventos):
    if not eventos:
        return
    por_idioma = {}
    for u in crud.usuarios_para_alertas(db):
        por_idioma.setdefault(normalizar(u.idioma), []).append(u.email)
    alerts.notificar(eventos, get_smtp_config(db), por_idioma, get_canais_config(db))


def checar_equipamento(ip: str, mode: str = "ip", config: Optional[dict] = None):
    """Verifica um equipamento por ping/TCP ou SNMPv3.
    Propaga SNMPUnavailableError quando o pysnmp não está instalado."""
    if mode != "snmpv3":
        return ping_equipamento(ip)  # função interna de ping (não a rota HTTP)
    config = {**(config or {}), "host": ip}
    try:
        return {"ip": ip, "status": "online", "tempo_ms": None, **snmp_test(config)}
    except SNMPUnavailableError:
        raise
    except Exception as exc:
        return {"ip": ip, "status": "offline", "tempo_ms": None, "error": str(exc)}


@app.post("/api/monitor")
def monitor_equipamento(request: MonitorRequest, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    equipment = None
    if request.equipmentId:
        equipment = crud.get_equipamento(db, request.equipmentId)
        if not equipment:
            raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    config = request.config or {}
    if request.mode == "snmpv3" and equipment and not config.get("authPassword"):
        config = abrir_config(equipment.monitor_config)
    try:
        result = checar_equipamento(request.ip, request.mode, config)
    except SNMPUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    evento = registrar_monitoramento(db, equipment, result)
    enviar_alertas(db, regras_alerta.aplicar(db, [evento] if evento else []))
    return result


# --- MONITORAMENTO EM SEGUNDO PLANO ---
# Mantém o status no banco atualizado mesmo sem nenhum Editor aberto,
# para que o link público (ex.: TV do NOC) mostre dados reais.
_monitor_stop = threading.Event()
_falhas_consecutivas = {}
_ultimo_ciclo = {"fim": None, "duracao": None, "equipamentos": 0}
_ultima_limpeza = {"momento": 0.0}


def _equipamento_monitoravel(eq):
    return eq.monitor_mode != "visual" and eq.status != "visual" and eq.ip and eq.ip != "Sem IP"


def _checar_seguro(alvo):
    eq_id, ip, mode, config = alvo
    try:
        return eq_id, checar_equipamento(ip, mode, config)
    except Exception as exc:
        logger.warning("Monitor: falha ao verificar %s (%s): %s", ip, mode, exc)
        return eq_id, None


def executar_ciclo_monitoramento():
    db = SessionLocal()
    try:
        alvos = [
            (eq.id, eq.ip, eq.monitor_mode or "ip", abrir_config(eq.monitor_config) if eq.monitor_mode == "snmpv3" else None)
            for eq in db.query(models.Equipamento).all() if _equipamento_monitoravel(eq)
        ]
    finally:
        db.close()
    inicio = time.monotonic()
    resultados = []
    if alvos:
        with ThreadPoolExecutor(max_workers=max(1, MONITOR_WORKERS)) as pool:
            resultados = list(pool.map(_checar_seguro, alvos))
    db = SessionLocal()
    eventos = []
    try:
        for eq_id, resultado in resultados:
            if resultado is None:
                continue
            # Recarrega: o mapa pode ter sido salvo (e o equipamento removido) durante o ciclo.
            equipamento = crud.get_equipamento(db, eq_id)
            if not equipamento:
                _falhas_consecutivas.pop(eq_id, None)
                continue
            if resultado.get("status") == "offline":
                falhas = _falhas_consecutivas.get(eq_id, 0) + 1
                _falhas_consecutivas[eq_id] = falhas
                # Equipamento estava online: só derruba após N falhas seguidas.
                if equipamento.status == "online" and falhas < MONITOR_FAILURE_THRESHOLD:
                    continue
            else:
                _falhas_consecutivas.pop(eq_id, None)
            evento = registrar_monitoramento(db, equipamento, resultado)
            if evento:
                eventos.append(evento)
        # Um único alerta por ciclo, mesmo que vários equipamentos mudem juntos; quedas "em cascata"
        # (uplink offline) e equipamentos em manutenção não geram alerta próprio.
        enviar_alertas(db, regras_alerta.aplicar(db, eventos))
        if time.monotonic() - _ultima_limpeza["momento"] > 3600:
            regras_alerta.limpar_manutencoes_vencidas(db)
        if HISTORY_RETENTION_DAYS > 0 and time.monotonic() - _ultima_limpeza["momento"] > 3600:
            _ultima_limpeza["momento"] = time.monotonic()
            apagados = crud.limpar_historico(db, HISTORY_RETENTION_DAYS)
            if apagados:
                logger.info("Histórico: %s registros com mais de %s dias removidos", apagados, HISTORY_RETENTION_DAYS)
    finally:
        db.close()
    _ultimo_ciclo.update(fim=datetime.utcnow(), duracao=round(time.monotonic() - inicio, 2), equipamentos=len(alvos))


def _loop_monitoramento():
    logger.info("Monitoramento em segundo plano ativo (intervalo: %ss)", MONITOR_INTERVAL)
    # Primeiro ciclo logo após iniciar, para não exibir status antigos por um intervalo inteiro.
    while True:
        try:
            executar_ciclo_monitoramento()
        except Exception:
            logger.exception("Erro no ciclo de monitoramento")
        if _monitor_stop.wait(MONITOR_INTERVAL):
            break


# --- RELATÓRIO DIÁRIO POR E-MAIL ---
_falhas_relatorio = {}  # user_id -> momento (monotonic) da última falha, para não tentar a cada minuto


def enviar_relatorio(db: Session, destinatarios, horas: int = 24, idioma: str = "en"):
    fuso = get_fuso(db)
    formato = "%d/%m/%Y %H:%M" if normalizar(idioma) == "pt" else "%Y-%m-%d %H:%M"
    formatar = lambda momento: momento.replace(tzinfo=timezone.utc).astimezone(fuso).strftime(formato)
    assunto, texto, html = email_service.montar_email_relatorio(crud.montar_relatorio(db, horas), formatar, normalizar(idioma))
    email_service.enviar_email(get_smtp_config(db), destinatarios, assunto, texto, html)


def verificar_relatorios_agendados(agora_utc: datetime = None):
    """Envia o relatório diário a quem chegou no horário escolhido e ainda não recebeu hoje."""
    db = SessionLocal()
    try:
        if not email_service.smtp_configurado(get_smtp_config(db)):
            return
        agora_local = (agora_utc or datetime.now(timezone.utc)).astimezone(get_fuso(db))
        hoje, hora = agora_local.strftime("%Y-%m-%d"), agora_local.strftime("%H:%M")
        for user in crud.listar_usuarios(db):
            if not (user.ativo and user.relatorio_diario and user.email):
                continue
            if user.ultimo_relatorio == hoje or hora < (user.relatorio_horario or "08:00"):
                continue
            if time.monotonic() - _falhas_relatorio.get(user.id, -1e9) < 1800:
                continue
            try:
                enviar_relatorio(db, [user.email], idioma=user.idioma)
                crud.atualizar_usuario(db, user.id, ultimo_relatorio=hoje)
                logger.info("Relatório diário enviado para %s", user.email)
            except Exception as exc:
                _falhas_relatorio[user.id] = time.monotonic()
                logger.warning("Falha ao enviar relatório diário para %s: %s", user.email, exc)
    finally:
        db.close()


# --- BACKUP AUTOMÁTICO ---
BACKUP_DIR_PADRAO = os.path.join(DATA_DIR, "backups")
_trava_backup = threading.Lock()
_falha_backup = {"momento": -1e9}


def get_backup_config(db: Session):
    c = crud.get_configuracoes(db, "backup.")
    try:
        manter = max(1, int(c.get("backup.manter") or 7))
    except ValueError:
        manter = 7
    return {
        "ativo": c.get("backup.ativo", "1") == "1",
        "diretorio": c.get("backup.diretorio") or BACKUP_DIR_PADRAO,
        "horario": c.get("backup.horario") or "03:00",
        "manter": manter,
        "ultimo": c.get("backup.ultimo") or None,
        "ultimo_erro": c.get("backup.ultimo_erro") or None,
    }


def fazer_backup(db: Session, agora_utc: datetime = None):
    cfg = get_backup_config(db)
    with _trava_backup:
        caminho = backup.criar_backup(db, DB_PATH, cfg["diretorio"], abrir_config, app.version)
        backup.limpar_antigos(cfg["diretorio"], cfg["manter"])
    momento = (agora_utc or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(tzinfo=None)
    crud.salvar_configuracoes(db, {"backup.ultimo": iso_utc(momento), "backup.ultimo_erro": ""})
    logger.info("Backup criado: %s", caminho)
    return caminho


def verificar_backup_agendado(agora_utc: datetime = None):
    """Um backup por dia, a partir do horário escolhido (no fuso configurado)."""
    db = SessionLocal()
    try:
        cfg = get_backup_config(db)
        if not cfg["ativo"] or not crud.listar_usuarios(db):
            return
        fuso = get_fuso(db)
        agora_local = (agora_utc or datetime.now(timezone.utc)).astimezone(fuso)
        if agora_local.strftime("%H:%M") < cfg["horario"]:
            return
        if cfg["ultimo"]:
            ultimo = datetime.fromisoformat(cfg["ultimo"].replace("Z", "+00:00"))
            if ultimo.tzinfo is None:
                ultimo = ultimo.replace(tzinfo=timezone.utc)
            if ultimo.astimezone(fuso).date() == agora_local.date():
                return
        if time.monotonic() - _falha_backup["momento"] < 1800:
            return
        try:
            fazer_backup(db, agora_utc)
        except Exception as exc:
            _falha_backup["momento"] = time.monotonic()
            crud.salvar_configuracoes(db, {"backup.ultimo_erro": f"{iso_utc(datetime.utcnow())} {exc}"})
            logger.warning("Falha no backup automático: %s", exc)
    finally:
        db.close()


class BackupConfigIn(BaseModel):
    ativo: bool = True
    diretorio: Optional[str] = None
    horario: str = "03:00"
    manter: int = 7


@app.get("/api/backup")
def obter_backup(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    cfg = get_backup_config(db)
    return {**cfg, "diretorio_padrao": BACKUP_DIR_PADRAO, "arquivos": backup.listar_backups(cfg["diretorio"])}


@app.put("/api/backup")
def salvar_backup_config(dados: BackupConfigIn, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", dados.horario or ""):
        raise HTTPException(status_code=400, detail="Horário inválido (use HH:MM).")
    if not 1 <= dados.manter <= 365:
        raise HTTPException(status_code=400, detail="Quantidade de backups deve ser entre 1 e 365.")
    diretorio = (dados.diretorio or "").strip() or BACKUP_DIR_PADRAO
    if not os.path.isabs(diretorio):
        raise HTTPException(status_code=400, detail="Use um caminho absoluto para a pasta de backup.")
    try:
        backup.testar_diretorio(diretorio)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Não foi possível gravar na pasta: {exc}")
    crud.salvar_configuracoes(db, {
        "backup.ativo": "1" if dados.ativo else "0",
        "backup.diretorio": "" if diretorio == BACKUP_DIR_PADRAO else diretorio,
        "backup.horario": dados.horario, "backup.manter": str(dados.manter),
    })
    return obter_backup(db, admin)


@app.post("/api/backup/agora")
def backup_agora(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    try:
        caminho = fazer_backup(db)
    except Exception as exc:
        crud.salvar_configuracoes(db, {"backup.ultimo_erro": f"{iso_utc(datetime.utcnow())} {exc}"})
        raise HTTPException(status_code=500, detail=f"Falha no backup: {exc}")
    return {"arquivo": os.path.basename(caminho), **obter_backup(db, admin)}


@app.get("/api/backup/arquivo/{nome}")
def baixar_backup(nome: str, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    if not backup.PADRAO_ARQUIVO.match(nome):
        raise HTTPException(status_code=404, detail="Backup não encontrado")
    caminho = os.path.join(get_backup_config(db)["diretorio"], nome)
    if not os.path.isfile(caminho):
        raise HTTPException(status_code=404, detail="Backup não encontrado")
    return FileResponse(caminho, media_type="application/zip", filename=nome)


def _loop_relatorios():
    while not _monitor_stop.wait(60):
        try:
            verificar_relatorios_agendados()
        except Exception:
            logger.exception("Erro ao verificar relatórios agendados")
        try:
            verificar_backup_agendado()
        except Exception:
            logger.exception("Erro ao verificar o backup agendado")


# --- MÉTRICAS SNMP (CPU, memória, temperatura, portas) ---
# Coletadas de equipamentos em SNMPv3 que estão online, a cada SNMP_METRICS_INTERVAL segundos.
SNMP_METRICS_INTERVAL = int(os.getenv("SNMP_METRICS_INTERVAL", "60"))
AMOSTRAS_PARA_ALERTAR = 3  # leituras seguidas acima do limite antes de alertar (evita picos)
_metricas = {}       # eq_id -> última coleta completa
_estado_snmp = {}    # eq_id -> contadores da coleta anterior (para calcular bit/s)
_limites_estado = {}  # (eq_id, métrica) -> {"acima": n, "alertado": bool}


def _metricas_compactas(m):
    return {
        "cpu": m.get("cpu_pct"), "mem": m.get("memoria_pct"), "temp": m.get("temperatura_c"), "uptime": m.get("uptime_s"),
        "coletado_em": m.get("coletado_em"),
        # [ordem, up, in_bps, out_bps, nome, alias, velocidade_mbps] das portas físicas
        "portas": [[i["ordem"], i["up"], i["in_bps"], i["out_bps"], i["nome"], i["alias"], i["velocidade_mbps"]]
                   for i in m.get("interfaces", []) if i.get("fisica")],
    }


def get_limites(db: Session):
    c = crud.get_configuracoes(db, "metricas.")
    def numero(chave, padrao):
        try:
            return float(c.get(chave)) if c.get(chave) not in (None, "") else padrao
        except ValueError:
            return padrao
    return {"temperatura": numero("metricas.limite_temp", 75.0), "cpu": numero("metricas.limite_cpu", 95.0)}


def avaliar_limites(eq, metricas, limites, projeto_nome=None):
    """Eventos de métrica acima do limite (após N leituras) e de volta ao normal (com folga)."""
    eventos = []
    for metrica, valor, folga in (("temperatura", metricas.get("temperatura_c"), 5), ("cpu", metricas.get("cpu_pct"), 10)):
        limite = limites.get(metrica) or 0
        estado = _limites_estado.setdefault((eq.id, metrica), {"acima": 0, "alertado": False})
        if not limite or valor is None:
            continue
        if valor >= limite:
            estado["acima"] += 1
            if estado["acima"] >= AMOSTRAS_PARA_ALERTAR and not estado["alertado"]:
                estado["alertado"] = True
                eventos.append(alerts.montar_evento_metrica(eq, projeto_nome, metrica, valor, limite, "alerta"))
        else:
            estado["acima"] = 0
            if estado["alertado"] and valor <= limite - folga:
                estado["alertado"] = False
                eventos.append(alerts.montar_evento_metrica(eq, projeto_nome, metrica, valor, limite, "normal"))
    return eventos


def _coletar_um(alvo):
    eq_id, ip, config = alvo
    cfg = {**(config or {}), "host": ip}
    try:
        return eq_id, metricas_snmp.coletar(lambda *oids: snmp_service.get(cfg, *oids),
                                            lambda oid: snmp_service.walk(cfg, oid), _estado_snmp.get(eq_id))
    except Exception as exc:
        logger.debug("Métricas SNMP de %s indisponíveis: %s", ip, exc)
        return eq_id, None


def executar_coleta_metricas():
    try:
        snmp_service._hlapi()
    except SNMPUnavailableError:
        return 0
    db = SessionLocal()
    try:
        equipamentos = db.query(models.Equipamento).filter(models.Equipamento.monitor_mode == "snmpv3").all()
        alvos = [(eq.id, eq.ip, abrir_config(eq.monitor_config)) for eq in equipamentos if eq.status == "online"]
    finally:
        db.close()
    if not alvos:
        return 0
    with ThreadPoolExecutor(max_workers=min(8, len(alvos)), thread_name_prefix="netcable-snmp") as pool:
        resultados = list(pool.map(_coletar_um, alvos))
    db = SessionLocal()
    eventos = []
    try:
        limites = get_limites(db)
        agora = datetime.utcnow()
        for eq_id, resultado in resultados:
            if not resultado:
                continue
            metricas, estado = resultado
            _estado_snmp[eq_id] = estado
            _metricas[eq_id] = {**metricas, "coletado_em": iso_utc(agora)}
            fisicas = [i for i in metricas["interfaces"] if i["fisica"]]
            soma = lambda campo: sum(i[campo] for i in fisicas if i[campo] is not None) if any(i[campo] is not None for i in fisicas) else None
            db.add(models.MetricaSnmp(equipamento_id=eq_id, criado_em=agora, cpu_pct=metricas["cpu_pct"], memoria_pct=metricas["memoria_pct"],
                                      temperatura_c=metricas["temperatura_c"], in_bps=soma("in_bps"), out_bps=soma("out_bps")))
            eq = crud.get_equipamento(db, eq_id)
            if eq and eq.notificar:
                eventos += avaliar_limites(eq, metricas, limites, eq.projeto.nome if eq.projeto else None)
        db.commit()
        enviar_alertas(db, regras_alerta.aplicar(db, eventos))
    finally:
        db.close()
    return len([r for _, r in resultados if r])


def _loop_metricas():
    while not _monitor_stop.wait(SNMP_METRICS_INTERVAL):
        try:
            executar_coleta_metricas()
        except Exception:
            logger.exception("Erro na coleta de métricas SNMP")


@app.on_event("startup")
def iniciar_tarefas():
    if MONITOR_INTERVAL > 0:
        threading.Thread(target=_loop_monitoramento, name="netcable-monitor", daemon=True).start()
        if SNMP_METRICS_INTERVAL > 0:
            threading.Thread(target=_loop_metricas, name="netcable-metricas", daemon=True).start()
    threading.Thread(target=_loop_relatorios, name="netcable-relatorios", daemon=True).start()


@app.on_event("shutdown")
def parar_tarefas():
    _monitor_stop.set()


class DiscoveryRequest(BaseModel):
    ip: str
    config: dict


@app.post("/api/discovery/neighbors")
def descobrir_vizinhos(request: DiscoveryRequest, user: models.Usuario = Depends(requer_editor)):
    config = {**request.config, "host": request.ip}
    try:
        return {"ip": request.ip, "neighbors": discover_neighbors(config)}
    except SNMPUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha na descoberta: {exc}")


# --- DESCOBERTA DA REDE (varredura de faixa) ---
class VarreduraIn(BaseModel):
    faixa: str


def _job_publico(db: Session, job):
    # Marca IPs que já estão em algum mapa (para não duplicar).
    no_mapa = {}
    for eq in db.query(models.Equipamento).filter(models.Equipamento.ip.in_([r["ip"] for r in job["resultados"]])).all():
        no_mapa.setdefault(eq.ip, set()).add(eq.projeto.nome if eq.projeto else "?")
    return {
        "id": job["id"], "status": job["status"], "fase": job["fase"], "total": job["total"], "verificados": job["verificados"],
        "erro": job["erro"], "duracao_s": round((job["fim"] or time.time()) - job["inicio"], 1),
        "resultados": [{**r, "no_mapa": sorted(no_mapa.get(r["ip"], []))} for r in job["resultados"]],
    }


@app.post("/api/descoberta")
def iniciar_descoberta(dados: VarreduraIn, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    try:
        ips = descoberta.validar_faixa(dados.faixa)
        job = descoberta.iniciar(ips, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    logger.info("%s iniciou varredura de %s (%d endereços)", user.username, dados.faixa, len(ips))
    return _job_publico(db, job)


@app.get("/api/descoberta/{job_id}")
def status_descoberta(job_id: str, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    job = descoberta.obter(job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Varredura não encontrada.")
    return _job_publico(db, job)


@app.delete("/api/descoberta/{job_id}")
def cancelar_descoberta(job_id: str, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    job = descoberta.cancelar(job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Varredura não encontrada.")
    return _job_publico(db, job)


# --- FUNÇÃO DE PING (TCP + ICMP com medição de tempo) ---
@app.get("/api/ping/{ip}")
def ping_rota(ip: str, user: models.Usuario = Depends(requer_editor)):
    # Exige login: sem isso qualquer pessoa usaria o servidor para varrer a rede interna.
    return ping_equipamento(ip)


# Pool compartilhado: as sondagens de cada equipamento rodam em paralelo.
_POOL_PING = ThreadPoolExecutor(max_workers=64, thread_name_prefix="netcable-ping")
PING_TIMEOUT = 1.5
PORTAS_TCP = (80, 443, 22)


def _sonda_tcp(ip, porta):
    inicio = time.perf_counter()
    try:
        with socket.create_connection((ip, porta), timeout=PING_TIMEOUT):
            return round((time.perf_counter() - inicio) * 1000, 2)
    except OSError:
        return None


def _sonda_icmp(ip):
    try:
        resposta = ping3.ping(ip, timeout=PING_TIMEOUT)
    except Exception:
        return None
    # ping3 devolve None (sem resposta) ou False (erro, ex.: sem permissão / host inválido).
    if resposta is None or resposta is False:
        return None
    return round(resposta * 1000, 2)


def ping_equipamento(ip: str):
    """Online se qualquer sonda responder (TCP 80/443/22 ou ICMP), todas em paralelo.
    Antes eram sequenciais: um equipamento fora do ar levava ~6 s para ser verificado."""
    sondas = [_POOL_PING.submit(_sonda_tcp, ip, porta) for porta in PORTAS_TCP]
    sondas.append(_POOL_PING.submit(_sonda_icmp, ip))
    try:
        for sonda in as_completed(sondas, timeout=PING_TIMEOUT + 1):
            tempo = sonda.result()
            if tempo is not None:
                return {"ip": ip, "status": "online", "tempo_ms": tempo}
    except Exception:
        pass
    finally:
        for sonda in sondas:
            sonda.cancel()
    return {"ip": ip, "status": "offline", "tempo_ms": None}


class EquipamentoCreate(BaseModel):
    id: str; nome: str; ip: str; tipo: str; status: str
    pingTime: Optional[float] = None; posX: float; posY: float; width: float; height: float
    monitorMode: str = "ip"; monitorConfig: Optional[dict] = None
    notificar: bool = True
    rackId: Optional[str] = None; rackU: Optional[int] = None; alturaU: Optional[int] = None
    modeloId: Optional[int] = None
    dependeDe: Optional[str] = None


class ConexaoCreate(BaseModel):
    id: str; source: str; target: str; label: Optional[str] = None
    sourceHandle: Optional[str] = None; targetHandle: Optional[str] = None


class MapaSchema(BaseModel):
    equipamentos: List[EquipamentoCreate]
    conexoes: List[ConexaoCreate]


def mesclar_config_snmp(eq, config_anterior_cifrada):
    """O frontend nunca recebe as senhas SNMP de volta; senha vazia significa
    "manter a atual". Mescla com a config anterior e devolve cifrado."""
    config = eq.get('monitorConfig') or {}
    if eq.get('monitorMode') != 'snmpv3':
        return proteger_config(config) if config else None
    anterior = abrir_config(config_anterior_cifrada)
    mesclada = {**anterior, **{k: v for k, v in config.items() if v not in (None, "")}}
    return proteger_config(mesclada)


@app.post("/api/projetos/{projeto_id}/salvar")
def salvar_projeto(projeto_id: int, mapa: MapaSchema, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    configs_anteriores = {eq.id: eq.monitor_config for eq in projeto.equipamentos}
    eq_dict = [eq.dict() for eq in mapa.equipamentos]
    ids_mapa = {eq['id'] for eq in eq_dict}
    for eq in eq_dict:
        eq['monitorConfig'] = mesclar_config_snmp(eq, configs_anteriores.get(eq['id']))
        # Uplink precisa ser outro equipamento deste mesmo mapa.
        if eq.get('dependeDe') not in ids_mapa or eq.get('dependeDe') == eq['id']:
            eq['dependeDe'] = None
    erro = crud.validar_racks(eq_dict)
    if erro:
        raise HTTPException(status_code=400, detail=erro)
    conn_dict = [conn.dict() for conn in mapa.conexoes]
    result = crud.salvar_mapa(db, projeto_id, eq_dict, conn_dict)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


class EquipamentoBase(BaseModel):
    id: str; nome: str; ip: str; tipo: str; status: str
    ping_time: Optional[float] = None; pos_x: float; pos_y: float; width: float; height: float
    monitor_mode: str = "ip"; monitor_config: Optional[dict] = None
    notificar: bool = True
    rack_id: Optional[str] = None; rack_u: Optional[int] = None; altura_u: Optional[int] = None
    modelo_id: Optional[int] = None
    depende_de: Optional[str] = None
    inalcancavel_por: Optional[str] = None  # uplink offline que explica a queda
    manutencao_ate: Optional[str] = None
    snmp: Optional[dict] = None  # métricas SNMP compactas (CPU, memória, temperatura, portas)
    class Config: from_attributes = True


class ConexaoBase(BaseModel):
    id: str; source: str; target: str; label: Optional[str] = None
    source_handle: Optional[str] = None; target_handle: Optional[str] = None
    class Config: from_attributes = True


class ModeloBase(BaseModel):
    id: int; nome: str; fabricante: Optional[str] = None; tipo: str
    altura_u: int; portas_rj45: int; portas_sfp: int; prefixo_porta: str = ""
    class Config: from_attributes = True


class ProjetoResponse(BaseModel):
    id: int; nome: str
    equipamentos: List[EquipamentoBase]; conexoes: List[ConexaoBase]
    modelos: List[ModeloBase] = []  # modelos usados neste mapa
    manutencao_ate: Optional[str] = None  # manutenção do projeto inteiro
    class Config: from_attributes = True


def _obter_dados_projeto(projeto_id: int, db: Session, projeto, publico: bool = False):
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    conexoes = db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).all()
    extras = _estado_alertas(db, projeto_id, projeto.equipamentos)
    equipamentos = []
    for equipamento in projeto.equipamentos:
        item = {column: getattr(equipamento, column) for column in ('id', 'nome', 'ip', 'tipo', 'status', 'ping_time', 'pos_x', 'pos_y', 'width', 'height', 'monitor_mode', 'notificar', 'rack_id', 'rack_u', 'altura_u', 'modelo_id', 'depende_de')}
        item.update(extras["por_equipamento"].get(equipamento.id, {}))
        config = abrir_config(equipamento.monitor_config)
        item['monitor_config'] = {} if publico else {key: value for key, value in config.items() if key not in ('authPassword', 'privPassword')}
        equipamentos.append(item)
    ids_modelos = {eq.modelo_id for eq in projeto.equipamentos if eq.modelo_id}
    modelos_usados = [m for m in crud.listar_modelos(db) if m.id in ids_modelos]
    return {"id": projeto.id, "nome": projeto.nome, "equipamentos": equipamentos, "conexoes": conexoes, "modelos": modelos_usados,
            "manutencao_ate": extras["manutencao_ate"]}


@app.get("/api/projetos/{projeto_id}/dados", response_model=ProjetoResponse)
def obter_dados_projeto(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return _obter_dados_projeto(projeto_id, db, projeto)


# --- BIBLIOTECA DE MODELOS DE EQUIPAMENTO ---
class ModeloIn(BaseModel):
    nome: str
    fabricante: Optional[str] = None
    tipo: str
    altura_u: int = 1
    portas_rj45: int = 0
    portas_sfp: int = 0
    prefixo_porta: str = ""


def _validar_modelo(dados: ModeloIn):
    nome = dados.nome.strip()
    if not 2 <= len(nome) <= 60:
        raise HTTPException(status_code=400, detail="O nome do modelo precisa ter de 2 a 60 caracteres.")
    if dados.tipo == "Rack":
        raise HTTPException(status_code=400, detail="Rack não é um modelo de equipamento.")
    if not 1 <= dados.altura_u <= 8:
        raise HTTPException(status_code=400, detail="Altura deve ser de 1U a 8U.")
    # Cabem até 2 fileiras de 24 portas RJ45 por U na frente desenhada.
    if not 0 <= dados.portas_rj45 <= 48 * dados.altura_u:
        raise HTTPException(status_code=400, detail=f"Para {dados.altura_u}U, use de 0 a {48 * dados.altura_u} portas RJ45.")
    if not 0 <= dados.portas_sfp <= 8:
        raise HTTPException(status_code=400, detail="Use de 0 a 8 portas SFP.")
    if len(dados.prefixo_porta) > 12:
        raise HTTPException(status_code=400, detail="Prefixo das portas muito longo (máx. 12).")
    return {**dados.dict(), "nome": nome, "fabricante": (dados.fabricante or "").strip() or None, "prefixo_porta": dados.prefixo_porta.strip()}


@app.get("/api/modelos", response_model=List[ModeloBase])
def listar_modelos(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    return crud.listar_modelos(db)


@app.post("/api/modelos", response_model=ModeloBase)
def criar_modelo(dados: ModeloIn, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    valores = _validar_modelo(dados)
    if crud.get_modelo_por_nome(db, valores["nome"]):
        raise HTTPException(status_code=400, detail="Já existe um modelo com esse nome.")
    return crud.salvar_modelo(db, valores)


@app.put("/api/modelos/{modelo_id}", response_model=ModeloBase)
def atualizar_modelo(modelo_id: int, dados: ModeloIn, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    valores = _validar_modelo(dados)
    existente = crud.get_modelo_por_nome(db, valores["nome"])
    if existente and existente.id != modelo_id:
        raise HTTPException(status_code=400, detail="Já existe um modelo com esse nome.")
    modelo = crud.salvar_modelo(db, valores, modelo_id)
    if not modelo:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    return modelo


@app.delete("/api/modelos/{modelo_id}")
def excluir_modelo(modelo_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    em_uso = crud.uso_do_modelo(db, modelo_id)
    if em_uso:
        raise HTTPException(status_code=400, detail=f"Modelo em uso por {em_uso} equipamento(s). Troque o modelo deles antes de excluir.")
    if not crud.deletar_modelo(db, modelo_id):
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    return {"status": "sucesso"}


# --- LINK PÚBLICO (token aleatório, revogável) ---
@app.get("/api/projetos/{projeto_id}/compartilhar")
def status_compartilhamento(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"token": projeto.share_token}


@app.post("/api/projetos/{projeto_id}/compartilhar")
def gerar_link_publico(projeto_id: int, regenerar: bool = False, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    if projeto.share_token and not regenerar:
        return {"token": projeto.share_token}
    projeto = crud.definir_share_token(db, projeto_id, secrets.token_urlsafe(24))
    return {"token": projeto.share_token}


@app.delete("/api/projetos/{projeto_id}/compartilhar")
def revogar_link_publico(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    if not crud.definir_share_token(db, projeto_id, None):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"status": "sucesso"}


@app.get("/api/public/mapas/{token}/dados", response_model=ProjetoResponse)
def obter_dados_projeto_publico(token: str, db: Session = Depends(get_db)):
    projeto = crud.get_projeto_por_token(db, token)
    if not projeto:
        raise HTTPException(status_code=404, detail="Link inválido ou revogado")
    return _obter_dados_projeto(projeto.id, db, projeto, publico=True)


# --- HISTÓRICO, STATUS E MÉTRICAS ---
@app.get("/api/projetos/{projeto_id}/historico")
def historico_projeto(projeto_id: int, limite: int = 100, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    limite = max(1, min(limite, 500))
    historico = crud.get_historico(db, projeto_id, limite)
    if historico is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return [{
        "equipamento_id": item.equipamento_id,
        "equipamento_nome": nome,
        "status": item.status,
        "tempo_ms": item.tempo_ms,
        "criado_em": iso_utc(item.criado_em),
    } for item, nome in historico]


@app.get("/api/projetos/{projeto_id}/status")
def status_projeto(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Status atual de cada equipamento, mantido pelo monitor do backend.
    O Editor consulta esta rota em vez de pingar cada equipamento."""
    linhas = crud.get_status_projeto(db, projeto_id)
    if linhas is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    extras = _estado_alertas(db, projeto_id)
    return {
        "monitor_ativo": MONITOR_INTERVAL > 0,
        "ultimo_ciclo": iso_utc(_ultimo_ciclo["fim"]),
        "manutencao_ate": extras["manutencao_ate"],
        "equipamentos": [{"id": eq_id, "status": status, "ping_time": ping, **extras["por_equipamento"].get(eq_id, {})}
                         for eq_id, status, ping in linhas],
    }


def _estado_alertas(db: Session, projeto_id: int, equipamentos=None):
    """Inalcançáveis (uplink offline) e janelas de manutenção ativas de um projeto."""
    if equipamentos is None:
        equipamentos = db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).all()
    projetos, por_eq = regras_alerta.manutencoes_ativas(db)
    extras = {}
    for eq_id, causa in regras_alerta.inalcancaveis(equipamentos).items():
        extras.setdefault(eq_id, {})["inalcancavel_por"] = causa
    for e in equipamentos:
        if e.id in por_eq:
            extras.setdefault(e.id, {})["manutencao_ate"] = iso_utc(por_eq[e.id])
        if e.id in _metricas:
            extras.setdefault(e.id, {})["snmp"] = _metricas_compactas(_metricas[e.id])
    return {"manutencao_ate": iso_utc(projetos.get(projeto_id)), "por_equipamento": extras}


class ManutencaoIn(BaseModel):
    horas: Optional[float] = None       # duração a partir de agora
    ate: Optional[datetime] = None      # ou um horário final (ISO)
    equipamento_id: Optional[str] = None
    motivo: Optional[str] = None


@app.get("/api/projetos/{projeto_id}/manutencao")
def listar_manutencao(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    if not crud.get_projeto(db, projeto_id):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return [{"id": m.id, "equipamento_id": m.equipamento_id, "ate": iso_utc(m.ate), "motivo": m.motivo}
            for m in regras_alerta.listar_manutencoes(db, projeto_id)]


@app.post("/api/projetos/{projeto_id}/manutencao")
def iniciar_manutencao(projeto_id: int, dados: ManutencaoIn, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    if not crud.get_projeto(db, projeto_id):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    agora = datetime.utcnow()
    if dados.ate:
        ate = dados.ate.astimezone(timezone.utc).replace(tzinfo=None) if dados.ate.tzinfo else dados.ate
    elif dados.horas:
        ate = agora + timedelta(hours=dados.horas)
    else:
        raise HTTPException(status_code=400, detail="Informe a duração da manutenção.")
    if not agora < ate <= agora + timedelta(days=30):
        raise HTTPException(status_code=400, detail="A manutenção deve terminar no futuro e durar no máximo 30 dias.")
    if dados.equipamento_id:
        eq = crud.get_equipamento(db, dados.equipamento_id)
        if not eq or eq.projeto_id != projeto_id:
            raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    m = regras_alerta.criar_manutencao(db, projeto_id, ate, dados.equipamento_id, (dados.motivo or "").strip()[:200] or None, user.id)
    logger.info("%s iniciou manutenção (projeto %s, equipamento %s) até %s", user.username, projeto_id, dados.equipamento_id, ate)
    return {"id": m.id, "equipamento_id": m.equipamento_id, "ate": iso_utc(m.ate), "motivo": m.motivo}


@app.delete("/api/projetos/{projeto_id}/manutencao")
def encerrar_manutencao(projeto_id: int, equipamento_id: Optional[str] = None, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    regras_alerta.cancelar_manutencao(db, projeto_id, equipamento_id)
    return {"status": "ok"}


@app.get("/api/projetos/{projeto_id}/disponibilidade")
def disponibilidade_projeto(projeto_id: int, horas: int = 24, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    horas = max(1, min(horas, 24 * 90))
    dados = crud.calcular_disponibilidade(db, projeto_id, horas)
    if dados is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"horas": horas, "equipamentos": dados}


@app.get("/api/projetos/{projeto_id}/equipamentos/{equipamento_id}/latencia")
def latencia_equipamento(projeto_id: int, equipamento_id: str, horas: int = 24, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    equipamento = crud.get_equipamento(db, equipamento_id)
    if not equipamento or equipamento.projeto_id != projeto_id:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    horas = max(1, min(horas, 24 * 90))
    pontos = crud.get_latencia(db, equipamento_id, horas)
    return {
        "equipamento_id": equipamento.id, "nome": equipamento.nome, "ip": equipamento.ip, "horas": horas,
        "pontos": [{"t": iso_utc(p.criado_em), "status": p.status, "ms": p.tempo_ms} for p in pontos],
    }


@app.get("/api/projetos/{projeto_id}/equipamentos/{equipamento_id}/metricas")
def metricas_equipamento(projeto_id: int, equipamento_id: str, horas: int = 24, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    equipamento = crud.get_equipamento(db, equipamento_id)
    if not equipamento or equipamento.projeto_id != projeto_id:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    horas = max(1, min(horas, 24 * 90))
    limite = datetime.utcnow() - timedelta(hours=horas)
    pontos = db.query(models.MetricaSnmp).filter(models.MetricaSnmp.equipamento_id == equipamento_id, models.MetricaSnmp.criado_em >= limite).order_by(models.MetricaSnmp.criado_em).all()
    return {
        "equipamento_id": equipamento.id, "nome": equipamento.nome, "ip": equipamento.ip, "horas": horas,
        "snmp": equipamento.monitor_mode == "snmpv3", "intervalo_s": SNMP_METRICS_INTERVAL,
        "atual": _metricas.get(equipamento_id), "limites": get_limites(db),
        "historico": [{"t": iso_utc(p.criado_em), "cpu": p.cpu_pct, "mem": p.memoria_pct, "temp": p.temperatura_c,
                       "in": p.in_bps, "out": p.out_bps} for p in pontos],
    }


class LimitesIn(BaseModel):
    temperatura: float = 75
    cpu: float = 95


@app.get("/api/config/metricas")
def obter_limites(db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    return get_limites(db)


@app.put("/api/config/metricas")
def salvar_limites(dados: LimitesIn, db: Session = Depends(get_db), admin: models.Usuario = Depends(requer_admin)):
    if not (0 <= dados.temperatura <= 150 and 0 <= dados.cpu <= 100):
        raise HTTPException(status_code=400, detail="Limites inválidos (temperatura 0–150 °C, CPU 0–100%; 0 desativa).")
    crud.salvar_configuracoes(db, {"metricas.limite_temp": str(dados.temperatura), "metricas.limite_cpu": str(dados.cpu)})
    return get_limites(db)


# --- INTERFACE WEB (imagem única) ---
# Quando a pasta com o build do frontend existe (imagem Docker única, versão Windows),
# o próprio backend serve a interface: uma porta só para tudo. No desenvolvimento
# (Vite em 5173) e na imagem separada (Nginx) esta parte simplesmente não é ativada.
PASTA_WEB = os.path.abspath(os.getenv("NETCABLE_STATIC_DIR") or os.path.join(os.path.dirname(__file__), "..", "static"))
if os.path.isfile(os.path.join(PASTA_WEB, "index.html")):
    from fastapi.responses import FileResponse

    @app.get("/{caminho:path}", include_in_schema=False)
    def interface_web(caminho: str):
        if caminho.startswith("api/") or caminho == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        arquivo = os.path.abspath(os.path.join(PASTA_WEB, caminho))
        if caminho and arquivo.startswith(PASTA_WEB + os.sep) and os.path.isfile(arquivo):
            # Arquivos com hash no nome (assets/) nunca mudam: cache longo.
            cache = "public, max-age=31536000, immutable" if caminho.startswith("assets/") else "no-cache"
            return FileResponse(arquivo, headers={"Cache-Control": cache})
        # Rotas do React (/projects, /editor/1, /share/...) recebem o index.html.
        return FileResponse(os.path.join(PASTA_WEB, "index.html"), headers={"Cache-Control": "no-cache"})
