from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import ping3
import socket
import time # Importação necessária para medir o tempo
import os
import json
import base64
import hashlib
import logging
from collections import defaultdict
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel
from typing import List, Optional
from .snmp_service import test as snmp_test, discover_neighbors, SNMPUnavailableError

from . import models, crud
from .database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

# Compatibilidade com bancos SQLite criados antes do suporte a SNMP.
with engine.begin() as connection:
    columns = {column[1] for column in connection.exec_driver_sql("PRAGMA table_info(equipamentos)")}
    if "monitor_mode" not in columns:
        connection.exec_driver_sql("ALTER TABLE equipamentos ADD COLUMN monitor_mode VARCHAR DEFAULT 'ip'")
    if "monitor_config" not in columns:
        connection.exec_driver_sql("ALTER TABLE equipamentos ADD COLUMN monitor_config VARCHAR")
    project_columns = {column[1] for column in connection.exec_driver_sql("PRAGMA table_info(projetos)")}
    if "user_id" not in project_columns:
        connection.exec_driver_sql("ALTER TABLE projetos ADD COLUMN user_id INTEGER")

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
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "").strip()
ALERT_WEBHOOK_TIMEOUT = float(os.getenv("ALERT_WEBHOOK_TIMEOUT", "3"))
logger = logging.getLogger("netcable")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

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
        "security": {
            "secret_key_configured": SECRET_KEY != "dev-only-change-this-secret",
            "default_admin_password": ADMIN_PASSWORD in {"admin", "altere_esta_senha"},
        },
    }

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
    if user is None:
        raise credentials_exception
    return user

# --- CRIAÇÃO DO USUÁRIO ADMIN (COM VARIÁVEIS DE AMBIENTE) ---
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

db_init = SessionLocal()
if not crud.get_usuario(db_init, ADMIN_USER):
    crud.criar_usuario(db_init, ADMIN_USER, pwd_context.hash(ADMIN_PASSWORD), "admin@netcable.local")
admin_user = crud.get_usuario(db_init, ADMIN_USER)
db_init.query(models.Projeto).filter(models.Projeto.user_id.is_(None)).update({"user_id": admin_user.id})
db_init.commit()
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
    login_failures.pop(form_data.username, None)
    access_token = criar_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/me")
def read_users_me(current_user: models.Usuario = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}

class PerfilUpdate(BaseModel):
    email: Optional[str] = None
    senha_atual: Optional[str] = None
    nova_senha: Optional[str] = None

@app.put("/api/me/perfil")
def atualizar_perfil_usuario(dados: PerfilUpdate, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    nova_hash = None
    if dados.nova_senha:
        if len(dados.nova_senha) < 8:
            raise HTTPException(status_code=400, detail="A nova senha precisa ter pelo menos 8 caracteres.")
        if not dados.senha_atual or not verificar_senha(dados.senha_atual, user.password_hash):
            raise HTTPException(status_code=400, detail="Senha atual incorreta.")
        nova_hash = pwd_context.hash(dados.nova_senha)
    
    user_atualizado = crud.atualizar_perfil(
        db, user.id, 
        novo_email=dados.email if dados.email else None, 
        nova_senha_hash=nova_hash
    )
    return {"status": "sucesso", "email": user_atualizado.email}

@app.get("/api/projetos")
def listar_projetos(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    return crud.get_projetos(db, user.id)

@app.post("/api/projetos")
def novo_projeto(nome: str, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    return crud.criar_projeto(db, nome, user.id)

@app.put("/api/projetos/{projeto_id}")
def editar_nome_projeto(projeto_id: int, novo_nome: str, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = crud.atualizar_projeto_nome(db, projeto_id, novo_nome, user.id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return projeto

@app.delete("/api/projetos/{projeto_id}")
def deletar_projeto_rota(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    if crud.deletar_projeto(db, projeto_id, user.id):
        return {"status": "sucesso"}
    raise HTTPException(status_code=404, detail="Projeto não encontrado")

# --- MONITORAMENTO E DESCOBERTA ---
class MonitorRequest(BaseModel):
    equipmentId: Optional[str] = None
    ip: str
    mode: str = "ip"
    config: Optional[dict] = None

def registrar_monitoramento(db: Session, equipamento, resultado):
    if not equipamento:
        return
    _, mudou, status_anterior = crud.registrar_status(
        db, equipamento.id, resultado.get("status", "offline"), resultado.get("tempo_ms")
    )
    if mudou and resultado.get("status") == "offline" and ALERT_WEBHOOK_URL:
        try:
            requests.post(ALERT_WEBHOOK_URL, json={
                "evento": "equipamento_offline",
                "equipamento": equipamento.nome,
                "ip": equipamento.ip,
                "status_anterior": status_anterior,
                "status": "offline",
            }, timeout=ALERT_WEBHOOK_TIMEOUT)
        except Exception as exc:
            logger.warning("Falha ao enviar alerta webhook: %s", exc)

@app.post("/api/monitor")
def monitor_equipamento(request: MonitorRequest, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    equipment = None
    if request.equipmentId:
        equipment = crud.get_equipamento_do_usuario(db, request.equipmentId, user.id)
        if not equipment:
            raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    if request.mode != "snmpv3":
        result = ping_equipamento(request.ip)
        registrar_monitoramento(db, equipment, result)
        return result
    config = request.config or {}
    if request.equipmentId and not config.get("authPassword"):
        equipment = db.query(models.Equipamento).filter(models.Equipamento.id == request.equipmentId).first()
        config = abrir_config(equipment.monitor_config if equipment else None)
    config.update({"host": request.ip})
    try:
        result = snmp_test(config)
        result = {"ip": request.ip, "status": "online", "tempo_ms": None, **result}
        registrar_monitoramento(db, equipment, result)
        return result
    except SNMPUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        result = {"ip": request.ip, "status": "offline", "tempo_ms": None, "error": str(exc)}
        registrar_monitoramento(db, equipment, result)
        return result

class DiscoveryRequest(BaseModel):
    ip: str
    config: dict

@app.post("/api/discovery/neighbors")
def descobrir_vizinhos(request: DiscoveryRequest, user: models.Usuario = Depends(get_current_user)):
    config = {**request.config, "host": request.ip}
    try:
        return {"ip": request.ip, "neighbors": discover_neighbors(config)}
    except SNMPUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha na descoberta: {exc}")

# --- FUNÇÃO DE PING (TCP + ICMP com medição de tempo) ---
@app.get("/api/ping/{ip}")
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
                tempo_ms = round((fim - inicio) * 1000, 2)
                return {"ip": ip, "status": "online", "tempo_ms": tempo_ms}
        
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

class ConexaoCreate(BaseModel):
    id: str; source: str; target: str; label: Optional[str] = None
    sourceHandle: Optional[str] = None; targetHandle: Optional[str] = None

class MapaSchema(BaseModel):
    equipamentos: List[EquipamentoCreate]
    conexoes: List[ConexaoCreate]

@app.post("/api/projetos/{projeto_id}/salvar")
def salvar_projeto(projeto_id: int, mapa: MapaSchema, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    eq_dict = [eq.dict() for eq in mapa.equipamentos]
    for eq in eq_dict:
        eq['monitorConfig'] = proteger_config(eq.get('monitorConfig'))
    conn_dict = [conn.dict() for conn in mapa.conexoes]
    result = crud.salvar_mapa(db, projeto_id, eq_dict, conn_dict, user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result

class EquipamentoBase(BaseModel):
    id: str; nome: str; ip: str; tipo: str; status: str
    ping_time: Optional[float] = None; pos_x: float; pos_y: float; width: float; height: float
    monitor_mode: str = "ip"; monitor_config: Optional[dict] = None
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
        item = {column: getattr(equipamento, column) for column in ('id', 'nome', 'ip', 'tipo', 'status', 'ping_time', 'pos_x', 'pos_y', 'width', 'height', 'monitor_mode')}
        config = abrir_config(equipamento.monitor_config)
        item['monitor_config'] = {} if publico else {key: value for key, value in config.items() if key not in ('authPassword', 'privPassword')}
        equipamentos.append(item)
    return {"id": projeto.id, "nome": projeto.nome, "equipamentos": equipamentos, "conexoes": conexoes}

@app.get("/api/projetos/{projeto_id}/dados", response_model=ProjetoResponse)
def obter_dados_projeto(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = crud.get_projeto(db, projeto_id, user.id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return _obter_dados_projeto(projeto_id, db, projeto)

@app.get("/api/public/projetos/{projeto_id}/dados", response_model=ProjetoResponse)
def obter_dados_projeto_publico(projeto_id: int, db: Session = Depends(get_db)):
    projeto = db.query(models.Projeto).filter(models.Projeto.id == projeto_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return _obter_dados_projeto(projeto_id, db, projeto, publico=True)

@app.get("/api/projetos/{projeto_id}/historico")
def historico_projeto(projeto_id: int, limite: int = 100, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    limite = max(1, min(limite, 500))
    historico = crud.get_historico(db, projeto_id, user.id, limite)
    if historico is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return [{
        "equipamento_id": item.equipamento_id,
        "status": item.status,
        "tempo_ms": item.tempo_ms,
        "criado_em": item.criado_em.isoformat() if item.criado_em else None,
    } for item in historico]
