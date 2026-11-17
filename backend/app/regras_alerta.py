"""Regras que deixam os alertas mais inteligentes.

1. Dependência (uplink): cada equipamento pode apontar para o equipamento do qual depende
   (ex.: o switch onde está ligado). Se o uplink está offline, o equipamento fica
   "inalcançável": não gera alerta próprio e aparece listado no alerta do uplink.
2. Janelas de manutenção: silenciam os alertas de um equipamento ou de um projeto inteiro
   até um horário. O monitoramento e o histórico continuam normalmente.

Equipamentos cuja queda foi silenciada também não geram o alerta de "voltou", para não
chegar um "voltou" de algo que ninguém soube que caiu.
"""

from datetime import datetime

from . import models

MAX_PROFUNDIDADE = 32  # proteção contra ciclos (A depende de B que depende de A)

# IDs de equipamentos cuja queda foi silenciada (em memória; reiniciar o NetCable só pode
# causar, no máximo, um "voltou" a mais).
_suprimidos = set()


def causa_raiz(eq_id, por_id):
    """Uplink offline mais próximo da raiz na cadeia de dependências, ou None."""
    causa = None
    visitados = {eq_id}
    atual = por_id.get(eq_id)
    for _ in range(MAX_PROFUNDIDADE):
        pai_id = getattr(atual, "depende_de", None)
        if not pai_id or pai_id in visitados or pai_id not in por_id:
            break
        visitados.add(pai_id)
        atual = por_id[pai_id]
        if atual.status == "offline":
            causa = atual
    return causa


def inalcancaveis(equipamentos):
    """{id: id_da_causa} para equipamentos offline cujo uplink (direto ou indireto) está offline."""
    por_id = {e.id: e for e in equipamentos}
    resultado = {}
    for e in equipamentos:
        if e.status == "offline":
            causa = causa_raiz(e.id, por_id)
            if causa:
                resultado[e.id] = causa.id
    return resultado


# --------------------------------------------------------------------------- manutenção
def manutencoes_ativas(db, agora=None):
    """(projetos_em_manutencao: {projeto_id: ate}, equipamentos_em_manutencao: {eq_id: ate})."""
    agora = agora or datetime.utcnow()
    projetos, equipamentos = {}, {}
    for m in db.query(models.Manutencao).filter(models.Manutencao.ate > agora).all():
        alvo = equipamentos if m.equipamento_id else projetos
        chave = m.equipamento_id or m.projeto_id
        alvo[chave] = max(alvo.get(chave, m.ate), m.ate)
    return projetos, equipamentos


def em_manutencao(eq, ativas):
    projetos, equipamentos = ativas
    return eq.id in equipamentos or eq.projeto_id in projetos


def criar_manutencao(db, projeto_id, ate, equipamento_id=None, motivo=None, user_id=None):
    # Uma janela por alvo: a nova substitui a anterior.
    cancelar_manutencao(db, projeto_id, equipamento_id, commit=False)
    m = models.Manutencao(projeto_id=projeto_id, equipamento_id=equipamento_id, ate=ate, motivo=motivo, user_id=user_id)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def cancelar_manutencao(db, projeto_id, equipamento_id=None, commit=True):
    q = db.query(models.Manutencao).filter(models.Manutencao.projeto_id == projeto_id)
    q = q.filter(models.Manutencao.equipamento_id == equipamento_id) if equipamento_id else q.filter(models.Manutencao.equipamento_id.is_(None))
    apagadas = q.delete(synchronize_session=False)
    if commit:
        db.commit()
    return apagadas


def listar_manutencoes(db, projeto_id, agora=None):
    agora = agora or datetime.utcnow()
    return db.query(models.Manutencao).filter(
        models.Manutencao.projeto_id == projeto_id, models.Manutencao.ate > agora
    ).order_by(models.Manutencao.ate).all()


def limpar_manutencoes_vencidas(db, agora=None):
    agora = agora or datetime.utcnow()
    apagadas = db.query(models.Manutencao).filter(models.Manutencao.ate <= agora).delete(synchronize_session=False)
    db.commit()
    return apagadas


# --------------------------------------------------------------------------- filtro dos eventos
def aplicar(db, eventos, agora=None):
    """Recebe os eventos do ciclo (com 'equipamento_id') e devolve só os que devem ser enviados.
    Quedas de equipamentos inalcançáveis viram a lista 'dependentes' do evento do uplink."""
    if not eventos:
        return []
    projetos_ids = {e.get("projeto_id") for e in eventos if e.get("projeto_id") is not None}
    equipamentos = db.query(models.Equipamento).filter(models.Equipamento.projeto_id.in_(projetos_ids)).all() if projetos_ids else []
    por_id = {e.id: e for e in equipamentos}
    ativas = manutencoes_ativas(db, agora)
    por_equipamento = {e["equipamento_id"]: e for e in eventos if e.get("equipamento_id")}

    enviar = []
    for evento in eventos:
        eq = por_id.get(evento.get("equipamento_id"))
        if eq is None:
            enviar.append(evento)
            continue
        if evento.get("metrica"):
            # Temperatura/CPU: só a manutenção silencia.
            if not em_manutencao(eq, ativas):
                enviar.append(evento)
            continue
        if em_manutencao(eq, ativas):
            if evento["status"] == "offline":
                _suprimidos.add(eq.id)
            else:
                _suprimidos.discard(eq.id)
            continue
        if evento["status"] == "offline":
            causa = causa_raiz(eq.id, por_id)
            if causa:
                _suprimidos.add(eq.id)
                pai = por_equipamento.get(causa.id)
                if pai is not None:
                    pai.setdefault("dependentes", []).append(eq.nome)
                continue
        elif eq.id in _suprimidos:
            _suprimidos.discard(eq.id)
            # Voltou junto com o uplink: aparece no alerta de recuperação dele.
            pai_id = eq.depende_de
            visitados = {eq.id}
            while pai_id and pai_id not in visitados:
                visitados.add(pai_id)
                if pai_id in por_equipamento and por_equipamento[pai_id]["status"] == "online":
                    por_equipamento[pai_id].setdefault("dependentes", []).append(eq.nome)
                    break
                pai_id = getattr(por_id.get(pai_id), "depende_de", None)
            continue
        enviar.append(evento)
    return enviar
