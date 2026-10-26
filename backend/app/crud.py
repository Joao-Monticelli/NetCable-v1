from sqlalchemy.orm import Session
from . import models

# --- USUÁRIOS ---
def get_usuario(db: Session, username: str):
    return db.query(models.Usuario).filter(models.Usuario.username == username).first()

def criar_usuario(db: Session, username: str, password_hash: str, email: str = None):
    db_user = models.Usuario(username=username, password_hash=password_hash, email=email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def atualizar_perfil(db: Session, user_id: int, novo_email: str = None, nova_senha_hash: str = None):
    db_user = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
    if db_user:
        if novo_email is not None:
            db_user.email = novo_email
        if nova_senha_hash is not None:
            db_user.password_hash = nova_senha_hash
        db.commit()
        db.refresh(db_user)
    return db_user

# --- PROJETOS ---
def get_projetos(db: Session):
    return db.query(models.Projeto).all()

def criar_projeto(db: Session, nome: str):
    db_projeto = models.Projeto(nome=nome)
    db.add(db_projeto)
    db.commit()
    db.refresh(db_projeto)
    return db_projeto

def atualizar_projeto_nome(db: Session, projeto_id: int, novo_nome: str):
    db_projeto = db.query(models.Projeto).filter(models.Projeto.id == projeto_id).first()
    if db_projeto:
        db_projeto.nome = novo_nome
        db.commit()
        db.refresh(db_projeto)
    return db_projeto

def salvar_mapa(db: Session, projeto_id: int, equipamentos: list, conexoes: list):
    db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).delete()
    db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).delete()
    
    for eq in equipamentos:
        db_eq = models.Equipamento(
            id=eq['id'], projeto_id=projeto_id, nome=eq['nome'], 
            ip=eq['ip'], tipo=eq['tipo'], status=eq['status'],
            ping_time=eq.get('pingTime'), pos_x=eq['posX'], pos_y=eq['posY'],
            width=eq.get('width', 200), height=eq.get('height', 80)
        )
        db.add(db_eq)
        
    for conn in conexoes:
        db_conn = models.Conexao(
            id=conn['id'], projeto_id=projeto_id, 
            source=conn['source'], target=conn['target'], label=conn.get('label'),
            source_handle=conn.get('sourceHandle'),
            target_handle=conn.get('targetHandle')
        )
        db.add(db_conn)
        
    db.commit()
    return {"status": "sucesso"}

def deletar_projeto(db: Session, projeto_id: int):
    db_projeto = db.query(models.Projeto).filter(models.Projeto.id == projeto_id).first()
    if db_projeto:
        db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).delete()
        db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).delete()
        db.delete(db_projeto)
        db.commit()
        return True
    return False