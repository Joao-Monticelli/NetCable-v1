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
def get_projetos(db: Session, user_id: int):
    return db.query(models.Projeto).filter(models.Projeto.user_id == user_id).all()

def criar_projeto(db: Session, nome: str, user_id: int):
    db_projeto = models.Projeto(nome=nome, user_id=user_id)
    db.add(db_projeto)
    db.commit()
    db.refresh(db_projeto)
    return db_projeto

def get_projeto(db: Session, projeto_id: int, user_id: int):
    return db.query(models.Projeto).filter(
        models.Projeto.id == projeto_id, models.Projeto.user_id == user_id
    ).first()

def get_equipamento_do_usuario(db: Session, equipamento_id: str, user_id: int):
    return db.query(models.Equipamento).join(models.Projeto).filter(
        models.Equipamento.id == equipamento_id,
        models.Projeto.user_id == user_id,
    ).first()

def registrar_status(db: Session, equipamento_id: str, status: str, tempo_ms=None):
    ultimo = db.query(models.HistoricoStatus).filter(
        models.HistoricoStatus.equipamento_id == equipamento_id
    ).order_by(models.HistoricoStatus.criado_em.desc()).first()
    if ultimo and ultimo.status == status and ultimo.criado_em:
        from datetime import datetime
        if (datetime.utcnow() - ultimo.criado_em).total_seconds() < 60:
            return ultimo, False, ultimo.status
    mudou = ultimo is not None and ultimo.status != status
    registro = models.HistoricoStatus(
        equipamento_id=equipamento_id, status=status, tempo_ms=tempo_ms
    )
    db.add(registro)
    db.commit()
    return registro, mudou, ultimo.status if ultimo else None

def get_historico(db: Session, projeto_id: int, user_id: int, limite: int = 100):
    if not get_projeto(db, projeto_id, user_id):
        return None
    return db.query(models.HistoricoStatus).join(models.Equipamento).filter(
        models.Equipamento.projeto_id == projeto_id
    ).order_by(models.HistoricoStatus.criado_em.desc()).limit(limite).all()

def atualizar_projeto_nome(db: Session, projeto_id: int, novo_nome: str, user_id: int):
    db_projeto = get_projeto(db, projeto_id, user_id)
    if db_projeto:
        db_projeto.nome = novo_nome
        db.commit()
        db.refresh(db_projeto)
    return db_projeto

def salvar_mapa(db: Session, projeto_id: int, equipamentos: list, conexoes: list, user_id: int):
    if not get_projeto(db, projeto_id, user_id):
        return None
    previous_configs = {
        item.id: item.monitor_config
        for item in db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).all()
    }
    db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).delete()
    db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).delete()
    
    for eq in equipamentos:
        config = eq.get('monitorConfig')
        if eq.get('monitorMode', 'ip') == 'snmpv3' and config and not config.get('authPassword') and not config.get('privPassword'):
            config = previous_configs.get(eq['id'], config)
        db_eq = models.Equipamento(
            id=eq['id'], projeto_id=projeto_id, nome=eq['nome'], 
            ip=eq['ip'], tipo=eq['tipo'], status=eq['status'],
            ping_time=eq.get('pingTime'), pos_x=eq['posX'], pos_y=eq['posY'],
            width=eq.get('width', 200), height=eq.get('height', 80),
            monitor_mode=eq.get('monitorMode', 'ip'),
            monitor_config=config
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

def deletar_projeto(db: Session, projeto_id: int, user_id: int):
    db_projeto = get_projeto(db, projeto_id, user_id)
    if db_projeto:
        db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).delete()
        db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).delete()
        db.delete(db_projeto)
        db.commit()
        return True
    return False
