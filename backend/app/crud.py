from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from . import models

# Mesmo sem mudança de status, grava um ponto no histórico a cada N segundos
# (guarda a latência ao longo do tempo sem inflar o banco).
HISTORICO_HEARTBEAT_SEGUNDOS = 300

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

def atualizar_status_equipamento(db: Session, equipamento_id: str, status: str, tempo_ms=None):
    """Atualiza o status atual do equipamento (o que a visualização pública lê).
    Não faz commit: é persistido junto com o histórico em registrar_status."""
    db.query(models.Equipamento).filter(models.Equipamento.id == equipamento_id).update(
        {"status": status, "ping_time": tempo_ms}, synchronize_session=False
    )

def get_projeto_por_token(db: Session, token: str):
    if not token:
        return None
    return db.query(models.Projeto).filter(models.Projeto.share_token == token).first()

def definir_share_token(db: Session, projeto_id: int, user_id: int, token):
    db_projeto = get_projeto(db, projeto_id, user_id)
    if db_projeto:
        db_projeto.share_token = token
        db.commit()
        db.refresh(db_projeto)
    return db_projeto

def registrar_status(db: Session, equipamento_id: str, status: str, tempo_ms=None):
    ultimo = db.query(models.HistoricoStatus).filter(
        models.HistoricoStatus.equipamento_id == equipamento_id
    ).order_by(models.HistoricoStatus.criado_em.desc()).first()
    if ultimo and ultimo.status == status and ultimo.criado_em:
        if (datetime.utcnow() - ultimo.criado_em).total_seconds() < HISTORICO_HEARTBEAT_SEGUNDOS:
            db.commit()  # persiste eventual atualização pendente do status atual
            return ultimo, False, ultimo.status
    mudou = ultimo is not None and ultimo.status != status
    registro = models.HistoricoStatus(
        equipamento_id=equipamento_id, status=status, tempo_ms=tempo_ms
    )
    db.add(registro)
    db.commit()
    return registro, mudou, ultimo.status if ultimo else None

def get_historico(db: Session, projeto_id: int, user_id: int, limite: int = 100):
    """Retorna [(HistoricoStatus, nome_do_equipamento)], mais recentes primeiro."""
    if not get_projeto(db, projeto_id, user_id):
        return None
    return db.query(models.HistoricoStatus, models.Equipamento.nome).join(models.Equipamento).filter(
        models.Equipamento.projeto_id == projeto_id
    ).order_by(models.HistoricoStatus.criado_em.desc()).limit(limite).all()

def calcular_disponibilidade(db: Session, projeto_id: int, user_id: int, horas: int = 24, agora: datetime = None):
    """Uptime ponderado pelo tempo na janela, por equipamento monitorado.

    Cada registro do histórico vale até o próximo registro (ou até agora).
    O último registro anterior à janela define o estado inicial."""
    if not get_projeto(db, projeto_id, user_id):
        return None
    agora = agora or datetime.utcnow()
    inicio = agora - timedelta(hours=horas)
    resultado = []
    equipamentos = db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).all()
    for eq in equipamentos:
        if eq.monitor_mode == "visual" or eq.status == "visual":
            continue
        anterior = db.query(models.HistoricoStatus).filter(
            models.HistoricoStatus.equipamento_id == eq.id, models.HistoricoStatus.criado_em < inicio
        ).order_by(models.HistoricoStatus.criado_em.desc()).first()
        registros = db.query(models.HistoricoStatus).filter(
            models.HistoricoStatus.equipamento_id == eq.id, models.HistoricoStatus.criado_em >= inicio
        ).order_by(models.HistoricoStatus.criado_em.asc()).all()
        pontos = ([(inicio, anterior.status)] if anterior else []) + [(r.criado_em, r.status) for r in registros]
        online = total = 0.0
        quedas = 0
        latencias = [r.tempo_ms for r in registros if r.tempo_ms is not None]
        for i, (momento, status) in enumerate(pontos):
            fim = pontos[i + 1][0] if i + 1 < len(pontos) else agora
            duracao = max(0.0, (fim - momento).total_seconds())
            total += duracao
            if status == "online":
                online += duracao
            if status == "offline" and i > 0 and pontos[i - 1][1] == "online":
                quedas += 1
        resultado.append({
            "equipamento_id": eq.id,
            "nome": eq.nome,
            "ip": eq.ip,
            "status": eq.status,
            "uptime_pct": round(online / total * 100, 2) if total > 0 else None,
            "quedas": quedas,
            "latencia_media_ms": round(sum(latencias) / len(latencias), 2) if latencias else None,
        })
    return resultado

def limpar_historico(db: Session, dias: int):
    """Remove registros mais antigos que `dias`. Retorna quantos foram apagados."""
    limite = datetime.utcnow() - timedelta(days=dias)
    apagados = db.query(models.HistoricoStatus).filter(models.HistoricoStatus.criado_em < limite).delete(synchronize_session=False)
    db.commit()
    return apagados

def get_status_projeto(db: Session, projeto_id: int, user_id: int):
    if not get_projeto(db, projeto_id, user_id):
        return None
    return db.query(models.Equipamento.id, models.Equipamento.status, models.Equipamento.ping_time).filter(
        models.Equipamento.projeto_id == projeto_id
    ).all()

def resumo_projetos(db: Session, user_id: int):
    """Lista os projetos do usuário com a contagem de equipamentos por status."""
    projetos = get_projetos(db, user_id)
    contagens = {}
    if projetos:
        linhas = db.query(models.Equipamento.projeto_id, models.Equipamento.status, func.count()).filter(
            models.Equipamento.projeto_id.in_([p.id for p in projetos])
        ).group_by(models.Equipamento.projeto_id, models.Equipamento.status).all()
        for projeto_id, status, quantidade in linhas:
            contagens.setdefault(projeto_id, {})[status] = quantidade
    return [{
        "id": p.id,
        "nome": p.nome,
        "compartilhado": bool(p.share_token),
        "online": contagens.get(p.id, {}).get("online", 0),
        "offline": contagens.get(p.id, {}).get("offline", 0),
        "visual": contagens.get(p.id, {}).get("visual", 0),
    } for p in projetos]

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
    # O status atual é responsabilidade do monitor do backend: para equipamentos
    # que já existiam com o mesmo IP, mantém o status do banco em vez do enviado
    # pelo navegador (que pode estar desatualizado).
    anteriores = {
        item.id: item
        for item in db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).all()
    }
    preservados = {
        eq_id: (item.ip, item.status, item.ping_time) for eq_id, item in anteriores.items()
    }
    db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).delete()
    db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).delete()

    for eq in equipamentos:
        status, ping_time = eq['status'], eq.get('pingTime')
        anterior = preservados.get(eq['id'])
        modo = eq.get('monitorMode', 'ip')
        if anterior and anterior[0] == eq['ip'] and modo != 'visual' and eq['status'] != 'visual' and anterior[1] != 'visual':
            status, ping_time = anterior[1], anterior[2]
        db_eq = models.Equipamento(
            id=eq['id'], projeto_id=projeto_id, nome=eq['nome'],
            ip=eq['ip'], tipo=eq['tipo'], status=status,
            ping_time=ping_time, pos_x=eq['posX'], pos_y=eq['posY'],
            width=eq.get('width', 200), height=eq.get('height', 80),
            monitor_mode=modo,
            monitor_config=eq.get('monitorConfig')  # já cifrado pelo main.py
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
        ids = [eq_id for (eq_id,) in db.query(models.Equipamento.id).filter(models.Equipamento.projeto_id == projeto_id)]
        if ids:
            db.query(models.HistoricoStatus).filter(models.HistoricoStatus.equipamento_id.in_(ids)).delete(synchronize_session=False)
        db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).delete()
        db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).delete()
        db.delete(db_projeto)
        db.commit()
        return True
    return False
