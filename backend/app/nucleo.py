"""Shared core of the API: settings, secret key and encryption, database session, login tokens and roles."""

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import jwt
from jwt import PyJWTError as JWTError
from passlib.context import CryptContext
import os
import re
import json
import logging
from cryptography.fernet import InvalidToken
from . import models, crud, alerts
from .database import engine, SessionLocal, DATA_DIR, DB_PATH
from . import migracoes, regras_alerta, segredos
from .segredos import CHAVE_DEV



models.Base.metadata.create_all(bind=engine)


# Atualiza bancos de versões anteriores (com cópia de segurança antes de migrar).
migracoes.aplicar(engine, DB_PATH)


def _versao():
    """APP_VERSION (definida no build da imagem) ou o arquivo VERSION do repositório."""
    if os.getenv("APP_VERSION"):
        return os.getenv("APP_VERSION")
    for caminho in (os.path.join(os.path.dirname(__file__), "..", "VERSION"), os.path.join(os.path.dirname(__file__), "..", "..", "VERSION")):
        if os.path.isfile(caminho):
            with open(caminho, encoding="utf-8") as f:
                return f.read().strip() + "-dev"
    return "dev"


VERSAO = _versao()


SECRET_KEY, CHAVE_CRIADA_AGORA = segredos.carregar_chave_secreta(DATA_DIR)


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


fernet = segredos.fernet_de(SECRET_KEY)


def _recifrar_segredos_antigos():
    """Instalações antigas cifravam senhas (SNMP/SMTP) com a chave de desenvolvimento.
    Ao gerar a chave nova, re-cifra o que ainda estiver na chave antiga para não perder nada."""
    antiga = segredos.fernet_de(CHAVE_DEV)
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
    return regras_alerta.fuso_do_sistema(db)


# --- AUTENTICAÇÃO E PAPÉIS ---
def verificar_senha(senha_plana, senha_hash):
    return pwd_context.verify(senha_plana, senha_hash)


def criar_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Credenciais inválidas")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        # "fase" marks a half-done login (password ok, 2FA code still missing): not a session.
        if username is None or payload.get("fase"):
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


USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{3,50}$")


HORARIO_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


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
