from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from . import models

# Mesmo sem mudança de status, grava um ponto no histórico a cada N segundos
# (guarda a latência ao longo do tempo sem inflar o banco).
HISTORICO_HEARTBEAT_SEGUNDOS = 300

# Modelo de equipe: todos os usuários enxergam todos os mapas. O que cada um
# pode fazer é decidido pelo papel (verificado nas rotas do main.py).


# --- USUÁRIOS ---
def get_usuario(db: Session, username: str):
    return db.query(models.Usuario).filter(models.Usuario.username == username).first()


def get_usuario_por_id(db: Session, user_id: int):
    return db.query(models.Usuario).filter(models.Usuario.id == user_id).first()


def listar_usuarios(db: Session):
    return db.query(models.Usuario).order_by(models.Usuario.username).all()


def criar_usuario(db: Session, username: str, password_hash: str, email: str = None, papel: str = "editor"):
    db_user = models.Usuario(username=username, password_hash=password_hash, email=email, papel=papel)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def contar_admins_ativos(db: Session, exceto_id: int = None):
    q = db.query(models.Usuario).filter(models.Usuario.papel == "admin", models.Usuario.ativo.is_(True))
    if exceto_id is not None:
        q = q.filter(models.Usuario.id != exceto_id)
    return q.count()


def atualizar_usuario(db: Session, user_id: int, **campos):
    db_user = get_usuario_por_id(db, user_id)
    if db_user:
        for campo, valor in campos.items():
            if valor is not None:
                setattr(db_user, campo, valor)
        db.commit()
        db.refresh(db_user)
    return db_user


def deletar_usuario(db: Session, user_id: int):
    db_user = get_usuario_por_id(db, user_id)
    if not db_user:
        return False
    # Os mapas são da equipe: mantém os projetos, só remove a autoria.
    db.query(models.Projeto).filter(models.Projeto.user_id == user_id).update({"user_id": None})
    db.delete(db_user)
    db.commit()
    return True


def usuarios_para_alertas(db: Session):
    return db.query(models.Usuario).filter(
        models.Usuario.ativo.is_(True), models.Usuario.receber_alertas.is_(True),
        models.Usuario.email.isnot(None), models.Usuario.email != "",
    ).all()


# --- CONFIGURAÇÕES DO SISTEMA ---
def get_configuracoes(db: Session, prefixo: str = ""):
    linhas = db.query(models.Configuracao).filter(models.Configuracao.chave.like(f"{prefixo}%")).all()
    return {linha.chave: linha.valor for linha in linhas}


def salvar_configuracoes(db: Session, valores: dict):
    for chave, valor in valores.items():
        linha = db.get(models.Configuracao, chave)
        if linha:
            linha.valor = valor
        else:
            db.add(models.Configuracao(chave=chave, valor=valor))
    db.commit()


# --- MODELOS DE EQUIPAMENTO ---
def listar_modelos(db: Session):
    return db.query(models.ModeloEquipamento).order_by(models.ModeloEquipamento.tipo, models.ModeloEquipamento.nome).all()


def get_modelo(db: Session, modelo_id: int):
    return db.query(models.ModeloEquipamento).filter(models.ModeloEquipamento.id == modelo_id).first()


def get_modelo_por_nome(db: Session, nome: str):
    return db.query(models.ModeloEquipamento).filter(func.lower(models.ModeloEquipamento.nome) == nome.lower()).first()


def salvar_modelo(db: Session, dados: dict, modelo_id: int = None):
    modelo = get_modelo(db, modelo_id) if modelo_id else models.ModeloEquipamento()
    if modelo is None:
        return None
    for campo, valor in dados.items():
        setattr(modelo, campo, valor)
    if not modelo_id:
        db.add(modelo)
    db.commit()
    db.refresh(modelo)
    return modelo


def uso_do_modelo(db: Session, modelo_id: int):
    return db.query(models.Equipamento).filter(models.Equipamento.modelo_id == modelo_id).count()


def deletar_modelo(db: Session, modelo_id: int):
    modelo = get_modelo(db, modelo_id)
    if not modelo:
        return False
    db.delete(modelo)
    db.commit()
    return True


# --- PROJETOS ---
def get_projetos(db: Session):
    return db.query(models.Projeto).order_by(models.Projeto.nome).all()


def criar_projeto(db: Session, nome: str, user_id: int = None):
    db_projeto = models.Projeto(nome=nome, user_id=user_id)
    db.add(db_projeto)
    db.commit()
    db.refresh(db_projeto)
    return db_projeto


def get_projeto(db: Session, projeto_id: int):
    return db.query(models.Projeto).filter(models.Projeto.id == projeto_id).first()


def get_equipamento(db: Session, equipamento_id: str):
    return db.query(models.Equipamento).filter(models.Equipamento.id == equipamento_id).first()


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


def definir_share_token(db: Session, projeto_id: int, token):
    db_projeto = get_projeto(db, projeto_id)
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


def get_historico(db: Session, projeto_id: int, limite: int = 100):
    """Retorna [(HistoricoStatus, nome_do_equipamento)], mais recentes primeiro."""
    if not get_projeto(db, projeto_id):
        return None
    return db.query(models.HistoricoStatus, models.Equipamento.nome).join(models.Equipamento).filter(
        models.Equipamento.projeto_id == projeto_id
    ).order_by(models.HistoricoStatus.criado_em.desc()).limit(limite).all()


def get_latencia(db: Session, equipamento_id: str, horas: int = 24, agora: datetime = None):
    """Pontos (horário, status, latência) de um equipamento na janela, em ordem cronológica."""
    agora = agora or datetime.utcnow()
    return db.query(models.HistoricoStatus).filter(
        models.HistoricoStatus.equipamento_id == equipamento_id,
        models.HistoricoStatus.criado_em >= agora - timedelta(hours=horas),
    ).order_by(models.HistoricoStatus.criado_em.asc()).all()


def _analisar_equipamento(db: Session, eq, inicio: datetime, agora: datetime):
    """Uptime ponderado pelo tempo, quedas, latência e mudanças de status na janela.

    Cada registro do histórico vale até o próximo registro (ou até agora).
    O último registro anterior à janela define o estado inicial."""
    anterior = db.query(models.HistoricoStatus).filter(
        models.HistoricoStatus.equipamento_id == eq.id, models.HistoricoStatus.criado_em < inicio
    ).order_by(models.HistoricoStatus.criado_em.desc()).first()
    registros = db.query(models.HistoricoStatus).filter(
        models.HistoricoStatus.equipamento_id == eq.id, models.HistoricoStatus.criado_em >= inicio
    ).order_by(models.HistoricoStatus.criado_em.asc()).all()
    pontos = ([(inicio, anterior.status)] if anterior else []) + [(r.criado_em, r.status) for r in registros]
    online = total = 0.0
    quedas = 0
    mudancas = []
    latencias = [r.tempo_ms for r in registros if r.tempo_ms is not None]
    for i, (momento, status) in enumerate(pontos):
        fim = pontos[i + 1][0] if i + 1 < len(pontos) else agora
        duracao = max(0.0, (fim - momento).total_seconds())
        total += duracao
        if status == "online":
            online += duracao
        if i > 0 and status != pontos[i - 1][1]:
            mudancas.append({"momento": momento, "de": pontos[i - 1][1], "para": status})
            if status == "offline" and pontos[i - 1][1] == "online":
                quedas += 1
    return {
        "equipamento_id": eq.id,
        "nome": eq.nome,
        "ip": eq.ip,
        "status": eq.status,
        "uptime_pct": round(online / total * 100, 2) if total > 0 else None,
        "quedas": quedas,
        "latencia_media_ms": round(sum(latencias) / len(latencias), 2) if latencias else None,
        "mudancas": mudancas,
    }


def _monitoravel(eq):
    return eq.monitor_mode != "visual" and eq.status != "visual"


def calcular_disponibilidade(db: Session, projeto_id: int, horas: int = 24, agora: datetime = None):
    if not get_projeto(db, projeto_id):
        return None
    agora = agora or datetime.utcnow()
    inicio = agora - timedelta(hours=horas)
    equipamentos = db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).all()
    resultado = []
    for eq in equipamentos:
        if _monitoravel(eq):
            dados = _analisar_equipamento(db, eq, inicio, agora)
            dados.pop("mudancas")
            resultado.append(dados)
    return resultado


def montar_relatorio(db: Session, horas: int = 24, agora: datetime = None):
    """Dados do relatório periódico: todos os mapas, com disponibilidade e eventos."""
    agora = agora or datetime.utcnow()
    inicio = agora - timedelta(hours=horas)
    mapas = []
    for projeto in get_projetos(db):
        itens = [_analisar_equipamento(db, eq, inicio, agora) for eq in projeto.equipamentos if _monitoravel(eq)]
        if itens:
            mapas.append({"nome": projeto.nome, "equipamentos": itens})
    return {"inicio": inicio, "fim": agora, "mapas": mapas}


def limpar_historico(db: Session, dias: int):
    """Remove registros mais antigos que `dias`. Retorna quantos foram apagados."""
    limite = datetime.utcnow() - timedelta(days=dias)
    apagados = db.query(models.HistoricoStatus).filter(models.HistoricoStatus.criado_em < limite).delete(synchronize_session=False)
    apagados += db.query(models.MetricaSnmp).filter(models.MetricaSnmp.criado_em < limite).delete(synchronize_session=False)
    db.commit()
    return apagados


def get_status_projeto(db: Session, projeto_id: int):
    if not get_projeto(db, projeto_id):
        return None
    return db.query(models.Equipamento.id, models.Equipamento.status, models.Equipamento.ping_time).filter(
        models.Equipamento.projeto_id == projeto_id
    ).all()


def resumo_projetos(db: Session):
    """Lista os projetos com a contagem de equipamentos por status."""
    projetos = get_projetos(db)
    contagens = {}
    if projetos:
        linhas = db.query(models.Equipamento.projeto_id, models.Equipamento.status, func.count()).filter(
            models.Equipamento.projeto_id.in_([p.id for p in projetos]),
            models.Equipamento.tipo != "Rack",  # o gabinete em si não é um equipamento monitorável
        ).group_by(models.Equipamento.projeto_id, models.Equipamento.status).all()
        for projeto_id, status, quantidade in linhas:
            contagens.setdefault(projeto_id, {})[status] = quantidade
    return [{
        "id": p.id,
        "nome": p.nome,
        "compartilhado": bool(p.share_token),
        "criado_por": p.usuario.username if p.usuario else None,
        "online": contagens.get(p.id, {}).get("online", 0),
        "offline": contagens.get(p.id, {}).get("offline", 0),
        "visual": contagens.get(p.id, {}).get("visual", 0),
    } for p in projetos]


def atualizar_projeto_nome(db: Session, projeto_id: int, novo_nome: str):
    db_projeto = get_projeto(db, projeto_id)
    if db_projeto:
        db_projeto.nome = novo_nome
        db.commit()
        db.refresh(db_projeto)
    return db_projeto


def validar_racks(equipamentos):
    """Confere que cada equipamento montado cabe no rack e não se sobrepõe a outro."""
    racks = {eq["id"]: eq for eq in equipamentos if eq["tipo"] == "Rack"}
    for rack in racks.values():
        if not rack.get("alturaU") or not 1 <= rack["alturaU"] <= 60:
            return f"Rack '{rack['nome']}': tamanho inválido (use de 1U a 60U)."
    ocupacao = {}
    for eq in equipamentos:
        if not eq.get("rackId"):
            continue
        rack = racks.get(eq["rackId"])
        if not rack:
            return f"'{eq['nome']}' está montado em um rack que não existe mais."
        u, altura = eq.get("rackU"), eq.get("alturaU")
        if not u or not altura or u < 1 or altura < 1 or u + altura - 1 > rack["alturaU"]:
            return f"'{eq['nome']}' não cabe no rack '{rack['nome']}' nessa posição."
        for posicao in range(u, u + altura):
            outro = ocupacao.setdefault(rack["id"], {}).get(posicao)
            if outro:
                return f"'{eq['nome']}' e '{outro}' ocupam o mesmo U{posicao} no rack '{rack['nome']}'."
            ocupacao[rack["id"]][posicao] = eq["nome"]
    return None


def salvar_mapa(db: Session, projeto_id: int, equipamentos: list, conexoes: list):
    if not get_projeto(db, projeto_id):
        return None
    # O status atual é responsabilidade do monitor do backend: para equipamentos
    # que já existiam com o mesmo IP, mantém o status do banco em vez do enviado
    # pelo navegador (que pode estar desatualizado).
    preservados = {
        item.id: (item.ip, item.status, item.ping_time)
        for item in db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).all()
    }
    db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).delete()
    db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).delete()

    for eq in equipamentos:
        status, ping_time = eq['status'], eq.get('pingTime')
        anterior = preservados.get(eq['id'])
        modo = eq.get('monitorMode', 'ip')
        if anterior and anterior[0] == eq['ip'] and modo != 'visual' and eq['status'] != 'visual' and anterior[1] != 'visual':
            status, ping_time = anterior[1], anterior[2]
        db.add(models.Equipamento(
            id=eq['id'], projeto_id=projeto_id, nome=eq['nome'],
            ip=eq['ip'], tipo=eq['tipo'], status=status,
            ping_time=ping_time, pos_x=eq['posX'], pos_y=eq['posY'],
            width=eq.get('width', 200), height=eq.get('height', 80),
            monitor_mode=modo,
            monitor_config=eq.get('monitorConfig'),  # já cifrado pelo main.py
            notificar=eq.get('notificar', True) is not False,
            rack_id=eq.get('rackId'), rack_u=eq.get('rackU'), altura_u=eq.get('alturaU'),
            modelo_id=eq.get('modeloId'), depende_de=eq.get('dependeDe') or None,
        ))

    for conn in conexoes:
        db.add(models.Conexao(
            id=conn['id'], projeto_id=projeto_id,
            source=conn['source'], target=conn['target'], label=conn.get('label'),
            source_handle=conn.get('sourceHandle'),
            target_handle=conn.get('targetHandle')
        ))

    db.commit()
    return {"status": "sucesso"}


def deletar_projeto(db: Session, projeto_id: int):
    db_projeto = get_projeto(db, projeto_id)
    if db_projeto:
        ids = [eq_id for (eq_id,) in db.query(models.Equipamento.id).filter(models.Equipamento.projeto_id == projeto_id)]
        if ids:
            db.query(models.HistoricoStatus).filter(models.HistoricoStatus.equipamento_id.in_(ids)).delete(synchronize_session=False)
        db.query(models.Conexao).filter(models.Conexao.projeto_id == projeto_id).delete()
        db.query(models.Manutencao).filter(models.Manutencao.projeto_id == projeto_id).delete()
        if ids:
            db.query(models.MetricaSnmp).filter(models.MetricaSnmp.equipamento_id.in_(ids)).delete(synchronize_session=False)
        db.query(models.Equipamento).filter(models.Equipamento.projeto_id == projeto_id).delete()
        db.delete(db_projeto)
        db.commit()
        return True
    return False
