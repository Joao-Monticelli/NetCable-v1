from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import ping3
from pydantic import BaseModel
from typing import List, Optional

from . import models, crud
from .database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="NetCable API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Libera para o link público funcionar
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"status": "API do NetCable rodando!"}

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
    id: str
    nome: str
    ip: str
    tipo: str
    status: str
    ping_time: Optional[float] = None
    pos_x: float
    pos_y: float
    width: float
    height: float

    class Config:
        from_attributes = True

class ConexaoBase(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None

    class Config:
        from_attributes = True

class ProjetoResponse(BaseModel):
    id: int
    nome: str
    equipamentos: List[EquipamentoBase]
    conexoes: List[ConexaoBase]

    class Config:
        from_attributes = True

class EquipamentoCreate(BaseModel):
    id: str
    nome: str
    ip: str
    tipo: str
    status: str
    pingTime: Optional[float] = None
    posX: float
    posY: float
    width: float
    height: float

class ConexaoCreate(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None

class MapaSchema(BaseModel):
    equipamentos: List[EquipamentoCreate]
    conexoes: List[ConexaoCreate]

@app.get("/api/projetos")
def listar_projetos(db: Session = Depends(get_db)):
    return crud.get_projetos(db)

@app.post("/api/projetos")
def novo_projeto(nome: str, db: Session = Depends(get_db)):
    return crud.criar_projeto(db, nome)

@app.post("/api/projetos/{projeto_id}/salvar")
def salvar_projeto(projeto_id: int, mapa: MapaSchema, db: Session = Depends(get_db)):
    equipamentos_dict = [eq.dict() for eq in mapa.equipamentos]
    conexoes_dict = [conn.dict() for conn in mapa.conexoes]
    return crud.salvar_mapa(db, projeto_id, equipamentos_dict, conexoes_dict)

@app.delete("/api/projetos/{projeto_id}")
def deletar_projeto_rota(projeto_id: int, db: Session = Depends(get_db)):
    sucesso = crud.deletar_projeto(db, projeto_id)
    if sucesso:
        return {"status": "sucesso", "mensagem": "Projeto deletado"}
    return {"status": "erro", "mensagem": "Projeto não encontrado"}

@app.get("/api/projetos/{projeto_id}/dados", response_model=ProjetoResponse)
def obter_dados_projeto(projeto_id: int, db: Session = Depends(get_db)):
    projeto = db.query(models.Projeto).filter(models.Projeto.id == projeto_id).first()
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    conexoes = db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).all()
    
    return {
        "id": projeto.id,
        "nome": projeto.nome,
        "equipamentos": projeto.equipamentos,
        "conexoes": conexoes
    }