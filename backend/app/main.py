from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import ping3
import os # Importação necessária para ler as variáveis
from pydantic import BaseModel
from typing import List, Optional

from . import models, crud
from .database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="NetCable API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "sua_chave_secreta_super_segura_aqui_mude_em_producao"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
db_init.close()

@app.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_usuario(db, form_data.username)
    if not user or not verificar_senha(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos")
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
    return crud.get_projetos(db)

@app.post("/api/projetos")
def novo_projeto(nome: str, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    return crud.criar_projeto(db, nome)

@app.put("/api/projetos/{projeto_id}")
def editar_nome_projeto(projeto_id: int, novo_nome: str, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    return crud.atualizar_projeto_nome(db, projeto_id, novo_nome)

@app.delete("/api/projetos/{projeto_id}")
def deletar_projeto_rota(projeto_id: int, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    if crud.deletar_projeto(db, projeto_id):
        return {"status": "sucesso"}
    raise HTTPException(status_code=404, detail="Projeto não encontrado")

class EquipamentoCreate(BaseModel):
    id: str; nome: str; ip: str; tipo: str; status: str
    pingTime: Optional[float] = None; posX: float; posY: float; width: float; height: float

class ConexaoCreate(BaseModel):
    id: str; source: str; target: str; label: Optional[str] = None
    sourceHandle: Optional[str] = None; targetHandle: Optional[str] = None

class MapaSchema(BaseModel):
    equipamentos: List[EquipamentoCreate]
    conexoes: List[ConexaoCreate]

@app.post("/api/projetos/{projeto_id}/salvar")
def salvar_projeto(projeto_id: int, mapa: MapaSchema, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    eq_dict = [eq.dict() for eq in mapa.equipamentos]
    conn_dict = [conn.dict() for conn in mapa.conexoes]
    return crud.salvar_mapa(db, projeto_id, eq_dict, conn_dict)

@app.get("/api/ping/{ip}")
def ping_equipamento(ip: str):
    try:
        resposta = ping3.ping(ip, timeout=2)
        if resposta is not None:
            return {"ip": ip, "status": "online", "tempo_ms": round(resposta * 1000, 2)}
        return {"ip": ip, "status": "offline", "tempo_ms": None}
    except Exception:
        return {"ip": ip, "status": "offline", "tempo_ms": None}

class EquipamentoBase(BaseModel):
    id: str; nome: str; ip: str; tipo: str; status: str
    ping_time: Optional[float] = None; pos_x: float; pos_y: float; width: float; height: float
    class Config: from_attributes = True

class ConexaoBase(BaseModel):
    id: str; source: str; target: str; label: Optional[str] = None
    source_handle: Optional[str] = None; target_handle: Optional[str] = None
    class Config: from_attributes = True

class ProjetoResponse(BaseModel):
    id: int; nome: str
    equipamentos: List[EquipamentoBase]; conexoes: List[ConexaoBase]
    class Config: from_attributes = True

@app.get("/api/projetos/{projeto_id}/dados", response_model=ProjetoResponse)
def obter_dados_projeto(projeto_id: int, db: Session = Depends(get_db)):
    projeto = db.query(models.Projeto).filter(models.Projeto.id == projeto_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    conexoes = db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).all()
    return {"id": projeto.id, "nome": projeto.nome, "equipamentos": projeto.equipamentos, "conexoes": conexoes}