from fastapi import FastAPI, Depends, HTTPException, Request
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
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel
from typing import List, Optional
from zoneinfo import ZoneInfo
from .snmp_service import test as snmp_test, discover_neighbors, SNMPUnavailableError

from . import models, crud, alerts, email_service
from .database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

# Compatibilidade com bancos SQLite criados por versões anteriores.
with engine.begin() as connection:
    def _colunas(tabela):
        return {column[1] for column in connection.exec_driver_sql(f"PRAGMA table_info({tabela})")}

    columns = _colunas("equipamentos")
    if "monitor_mode" not in columns:
        connection.exec_driver_sql("ALTER TABLE equipamentos ADD COLUMN monitor_mode VARCHAR DEFAULT 'ip'")
    if "monitor_config" not in columns:
        connection.exec_driver_sql("ALTER TABLE equipamentos ADD COLUMN monitor_config VARCHAR")
    if "notificar" not in columns:
        connection.exec_driver_sql("ALTER TABLE equipamentos ADD COLUMN notificar BOOLEAN NOT NULL DEFAULT 1")
    project_columns = _colunas("projetos")
    if "user_id" not in project_columns:
        connection.exec_driver_sql("ALTER TABLE projetos ADD COLUMN user_id INTEGER")
    if "share_token" not in project_columns:
        connection.exec_driver_sql("ALTER TABLE projetos ADD COLUMN share_token VARCHAR")
        connection.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_projetos_share_token ON projetos (share_token)")
    user_columns = _colunas("usuarios")
    # Usuários que já existiam (antes do modelo de equipe) viram admin.
    for coluna, ddl in [
        ("papel", "VARCHAR NOT NULL DEFAULT 'admin'"),
        ("ativo", "BOOLEAN NOT NULL DEFAULT 1"),
        ("receber_alertas", "BOOLEAN NOT NULL DEFAULT 0"),
        ("relatorio_diario", "BOOLEAN NOT NULL DEFAULT 0"),
        ("relatorio_horario", "VARCHAR NOT NULL DEFAULT '08:00'"),
        ("ultimo_relatorio", "VARCHAR"),
    ]:
        if coluna not in user_columns:
            connection.exec_driver_sql(f"ALTER TABLE usuarios ADD COLUMN {coluna} {ddl}")

app = FastAPI(title="NetCable API", version=os.getenv("APP_VERSION", "dev"))

ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["http://localhost", "http://localhost:3080", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
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


_fernet_key = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest())
fernet = Fernet(_fernet_key)


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
        "alerts": alerts.canais_configurados(get_smtp_config(db)) if database_ok else {},
        "history_retention_days": HISTORY_RETENTION_DAYS,
        "security": {
            "secret_key_configured": SECRET_KEY != "dev-only-change-this-secret",
            "default_admin_password": ADMIN_PASSWORD in {"admin", "altere_esta_senha"},
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


# --- USUÁRIO ADMIN INICIAL (VARIÁVEIS DE AMBIENTE) ---
# O usuário definido em ADMIN_USER é sempre garantido como admin ativo: serve
# também para recuperar o acesso caso alguém desative todos os administradores.
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

db_init = SessionLocal()
admin_user = crud.get_usuario(db_init, ADMIN_USER)
if not admin_user:
    crud.criar_usuario(db_init, ADMIN_USER, pwd_context.hash(ADMIN_PASSWORD), None, papel="admin")
elif admin_user.papel != "admin" or not admin_user.ativo:
    crud.atualizar_usuario(db_init, admin_user.id, papel="admin", ativo=True)
db_init.close()

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
        "relatorio_horario": u.relatorio_horario,
    }


@app.get("/api/me")
def read_users_me(current_user: models.Usuario = Depends(get_current_user)):
    return usuario_publico(current_user)


HORARIO_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{3,50}$")


class PerfilUpdate(BaseModel):
    email: Optional[str] = None
    senha_atual: Optional[str] = None
    nova_senha: Optional[str] = None
    receber_alertas: Optional[bool] = None
    relatorio_diario: Optional[bool] = None
    relatorio_horario: Optional[str] = None


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
    email = dados.email.strip() if dados.email is not None else None
    if (dados.receber_alertas or dados.relatorio_diario) and not (email if email is not None else user.email):
        raise HTTPException(status_code=400, detail="Informe um e-mail para receber alertas e relatórios.")
    atualizado = crud.atualizar_usuario(
        db, user.id, email=email, password_hash=nova_hash,
        receber_alertas=dados.receber_alertas, relatorio_diario=dados.relatorio_diario,
        relatorio_horario=dados.relatorio_horario,
    )
    return usuario_publico(atualizado)


@app.post("/api/me/relatorio/enviar")
def enviar_meu_relatorio(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Envia agora o relatório das últimas 24h para o e-mail do usuário (útil para testar)."""
    if not user.email:
        raise HTTPException(status_code=400, detail="Cadastre um e-mail no seu perfil primeiro.")
    try:
        enviar_relatorio(db, [user.email])
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
            get_smtp_config(db), [destino], "[NetCable] E-mail de teste",
            "Se você recebeu esta mensagem, o envio de e-mails do NetCable está funcionando.",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha no envio: {exc}")
    return {"status": "enviado", "para": destino}


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
    destinatarios = [u.email for u in crud.usuarios_para_alertas(db)]
    alerts.notificar(eventos, get_smtp_config(db), destinatarios)


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
    enviar_alertas(db, [evento] if evento else [])
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
        # Um único alerta por ciclo, mesmo que vários equipamentos mudem juntos.
        enviar_alertas(db, eventos)
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


def enviar_relatorio(db: Session, destinatarios, horas: int = 24):
    fuso = get_fuso(db)
    formatar = lambda momento: momento.replace(tzinfo=timezone.utc).astimezone(fuso).strftime("%d/%m/%Y %H:%M")
    assunto, texto, html = email_service.montar_email_relatorio(crud.montar_relatorio(db, horas), formatar)
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
                enviar_relatorio(db, [user.email])
                crud.atualizar_usuario(db, user.id, ultimo_relatorio=hoje)
                logger.info("Relatório diário enviado para %s", user.email)
            except Exception as exc:
                _falhas_relatorio[user.id] = time.monotonic()
                logger.warning("Falha ao enviar relatório diário para %s: %s", user.email, exc)
    finally:
        db.close()


def _loop_relatorios():
    while not _monitor_stop.wait(60):
        try:
            verificar_relatorios_agendados()
        except Exception:
            logger.exception("Erro ao verificar relatórios agendados")


@app.on_event("startup")
def iniciar_tarefas():
    if MONITOR_INTERVAL > 0:
        threading.Thread(target=_loop_monitoramento, name="netcable-monitor", daemon=True).start()
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


# --- FUNÇÃO DE PING (TCP + ICMP com medição de tempo) ---
@app.get("/api/ping/{ip}")
def ping_rota(ip: str, user: models.Usuario = Depends(requer_editor)):
    # Exige login: sem isso qualquer pessoa usaria o servidor para varrer a rede interna.
    return ping_equipamento(ip)


def ping_equipamento(ip: str):
    try:
        # 1. Tenta conectar em portas comuns (TCP) e mede o tempo
        for porta in [80, 443, 22]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            inicio = time.time()
            resultado = sock.connect_ex((ip, porta))
            fim = time.time()
            sock.close()
            if resultado == 0:
                return {"ip": ip, "status": "online", "tempo_ms": round((fim - inicio) * 1000, 2)}

        # 2. Se não conectou em nenhuma porta, tenta o ping ICMP tradicional
        resposta = ping3.ping(ip, timeout=1.5)
        if resposta is not None:
            return {"ip": ip, "status": "online", "tempo_ms": round(resposta * 1000, 2)}
        return {"ip": ip, "status": "offline", "tempo_ms": None}
    except Exception:
        return {"ip": ip, "status": "offline", "tempo_ms": None}


class EquipamentoCreate(BaseModel):
    id: str; nome: str; ip: str; tipo: str; status: str
    pingTime: Optional[float] = None; posX: float; posY: float; width: float; height: float
    monitorMode: str = "ip"; monitorConfig: Optional[dict] = None
    notificar: bool = True


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
    for eq in eq_dict:
        eq['monitorConfig'] = mesclar_config_snmp(eq, configs_anteriores.get(eq['id']))
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
    class Config: from_attributes = True


class ConexaoBase(BaseModel):
    id: str; source: str; target: str; label: Optional[str] = None
    source_handle: Optional[str] = None; target_handle: Optional[str] = None
    class Config: from_attributes = True


class ProjetoResponse(BaseModel):
    id: int; nome: str
    equipamentos: List[EquipamentoBase]; conexoes: List[ConexaoBase]
    class Config: from_attributes = True


def _obter_dados_projeto(projeto_id: int, db: Session, projeto, publico: bool = False):
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    conexoes = db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).all()
    equipamentos = []
    for equipamento in projeto.equipamentos:
        item = {column: getattr(equipamento, column) for column in ('id', 'nome', 'ip', 'tipo', 'status', 'ping_time', 'pos_x', 'pos_y', 'width', 'height', 'monitor_mode', 'notificar')}
        config = abrir_config(equipamento.monitor_config)
        item['monitor_config'] = {} if publico else {key: value for key, value in config.items() if key not in ('authPassword', 'privPassword')}
        equipamentos.append(item)
    return {"id": projeto.id, "nome": projeto.nome, "equipamentos": equipamentos, "conexoes": conexoes}


@app.get("/api/projetos/{projeto_id}/dados", response_model=ProjetoResponse)
def obter_dados_projeto(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return _obter_dados_projeto(projeto_id, db, projeto)


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
    return {
        "monitor_ativo": MONITOR_INTERVAL > 0,
        "ultimo_ciclo": iso_utc(_ultimo_ciclo["fim"]),
        "equipamentos": [{"id": eq_id, "status": status, "ping_time": ping} for eq_id, status, ping in linhas],
    }


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
