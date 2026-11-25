"""Regras que deixam os alertas mais inteligentes.

1. Dependência (uplink): cada equipamento pode apontar para o equipamento do qual depende
   (ex.: o switch onde está ligado). Se o uplink está offline, o equipamento fica
   "inalcançável": não gera alerta próprio e aparece listado no alerta do uplink.
2. Janelas de manutenção: silenciam os alertas de um equipamento ou de um projeto inteiro
   agora (até um horário), num período agendado ou toda semana (ex.: domingo 02:00 por 2 h, no
   fuso do sistema). O monitoramento e o histórico continuam normalmente.
3. Reconhecimento: alguém avisa "estou vendo" num equipamento offline; os lembretes param e a
   equipe vê quem assumiu. Some sozinho quando o equipamento volta.

Equipamentos cuja queda foi silenciada também não geram o alerta de "voltou", para não
chegar um "voltou" de algo que ninguém soube que caiu.
"""

import json
import logging
import os
from datetime import datetime, time as hora_do_dia, timedelta, timezone
from zoneinfo import ZoneInfo

from . import crud, models

logger = logging.getLogger("netcable.regras")
FUSO_PADRAO = os.getenv("TZ", "America/Sao_Paulo")
SEM_FIM = datetime(9999, 12, 31)  # `ate` of a weekly window with no end date

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
def fuso_do_sistema(db):
    """Time zone chosen by the admin (reports, weekly maintenance windows)."""
    nome = crud.get_configuracoes(db, "sistema.fuso").get("sistema.fuso") or FUSO_PADRAO
    try:
        return ZoneInfo(nome)
    except Exception:
        logger.warning("Fuso horário inválido '%s'; usando UTC.", nome)
        return timezone.utc


def ler_recorrencia(m):
    if not m.recorrencia:
        return None
    try:
        return json.loads(m.recorrencia)
    except ValueError:
        return None


def _utc_naive(momento):
    return momento.astimezone(timezone.utc).replace(tzinfo=None)


def ocorrencia_atual(rec, agora, fuso):
    """End (UTC, naive) of the weekly occurrence that covers `agora` (UTC, naive), or None."""
    local = agora.replace(tzinfo=timezone.utc).astimezone(fuso)
    h, m = (int(x) for x in rec["hora"].split(":"))
    duracao = timedelta(minutes=int(rec["minutos"]))
    for dias_atras in range(0, 2 + duracao.days):
        dia = local.date() - timedelta(days=dias_atras)
        if dia.weekday() not in rec["dias"]:
            continue
        inicio = datetime.combine(dia, hora_do_dia(h, m), tzinfo=fuso)
        if inicio <= local < inicio + duracao:
            return _utc_naive(inicio + duracao)
    return None


def proxima_ocorrencia(rec, agora, fuso):
    """Start (UTC, naive) of the next weekly occurrence after `agora`."""
    local = agora.replace(tzinfo=timezone.utc).astimezone(fuso)
    h, m = (int(x) for x in rec["hora"].split(":"))
    for dias in range(0, 8):
        dia = local.date() + timedelta(days=dias)
        inicio = datetime.combine(dia, hora_do_dia(h, m), tzinfo=fuso)
        if dia.weekday() in rec["dias"] and inicio > local:
            return _utc_naive(inicio)
    return None


def fim_se_ativa(m, agora, fuso):
    """End of the window `m` if it is silencing alerts right now (UTC, naive), else None."""
    if m.ate <= agora or (m.inicio and m.inicio > agora):
        return None
    rec = ler_recorrencia(m)
    if rec is None:
        return m.ate
    if rec.get("pular_ate") and agora < datetime.fromisoformat(rec["pular_ate"]):
        return None  # this occurrence was ended early
    fim = ocorrencia_atual(rec, agora, fuso)
    return min(fim, m.ate) if fim else None


def manutencoes_ativas(db, agora=None, fuso=None):
    """(projetos_em_manutencao: {projeto_id: ate}, equipamentos_em_manutencao: {eq_id: ate})."""
    agora = agora or datetime.utcnow()
    fuso = fuso or fuso_do_sistema(db)
    projetos, equipamentos = {}, {}
    for m in db.query(models.Manutencao).filter(models.Manutencao.ate > agora).all():
        fim = fim_se_ativa(m, agora, fuso)
        if fim is None:
            continue
        alvo = equipamentos if m.equipamento_id else projetos
        chave = m.equipamento_id or m.projeto_id
        alvo[chave] = max(alvo.get(chave, fim), fim)
    return projetos, equipamentos


def em_manutencao(eq, ativas):
    projetos, equipamentos = ativas
    return eq.id in equipamentos or eq.projeto_id in projetos


def criar_manutencao(db, projeto_id, ate, equipamento_id=None, motivo=None, user_id=None, inicio=None, recorrencia=None):
    if inicio is None and recorrencia is None:
        # "Agora": substitui a janela imediata anterior do mesmo alvo (as agendadas continuam).
        cancelar_manutencao(db, projeto_id, equipamento_id, commit=False)
    m = models.Manutencao(projeto_id=projeto_id, equipamento_id=equipamento_id, ate=ate, motivo=motivo, user_id=user_id,
                          inicio=inicio, recorrencia=json.dumps(recorrencia) if recorrencia else None)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _do_alvo(db, projeto_id, equipamento_id):
    q = db.query(models.Manutencao).filter(models.Manutencao.projeto_id == projeto_id)
    return q.filter(models.Manutencao.equipamento_id == equipamento_id) if equipamento_id else q.filter(models.Manutencao.equipamento_id.is_(None))


def cancelar_manutencao(db, projeto_id, equipamento_id=None, commit=True, agora=None, fuso=None):
    """Ends the maintenance that is silencing the target now: deletes one-off windows that already
    started and skips the current occurrence of weekly ones. Future windows are kept."""
    agora = agora or datetime.utcnow()
    afetadas = 0
    for m in _do_alvo(db, projeto_id, equipamento_id).all():
        rec = ler_recorrencia(m)
        if rec is None:
            if m.inicio is None or m.inicio <= agora:
                db.delete(m)
                afetadas += 1
            continue
        fim = fim_se_ativa(m, agora, fuso or fuso_do_sistema(db))
        if fim:
            rec["pular_ate"] = fim.isoformat()
            m.recorrencia = json.dumps(rec)
            afetadas += 1
    if commit:
        db.commit()
    return afetadas


def remover_manutencao(db, projeto_id, manutencao_id):
    m = db.query(models.Manutencao).filter(models.Manutencao.id == manutencao_id, models.Manutencao.projeto_id == projeto_id).first()
    if not m:
        return None
    db.delete(m)
    db.commit()
    return m


def listar_manutencoes(db, projeto_id, agora=None):
    agora = agora or datetime.utcnow()
    return db.query(models.Manutencao).filter(
        models.Manutencao.projeto_id == projeto_id, models.Manutencao.ate > agora
    ).order_by(models.Manutencao.inicio, models.Manutencao.ate).all()


# --------------------------------------------------------------------------- reconhecimento
def reconhecer(db, equipamento, usuario, nota=None):
    r = db.get(models.Reconhecimento, equipamento.id) or models.Reconhecimento(equipamento_id=equipamento.id)
    r.projeto_id, r.usuario, r.nota, r.criado_em = equipamento.projeto_id, usuario, nota, datetime.utcnow()
    db.merge(r)
    db.commit()
    return db.get(models.Reconhecimento, equipamento.id)


def remover_reconhecimento(db, equipamento_id, commit=True):
    """Returns the removed acknowledgement (or None)."""
    r = db.get(models.Reconhecimento, equipamento_id)
    if r:
        db.delete(r)
        if commit:
            db.commit()
    return r


def limpar_reconhecimentos_orfaos(db):
    """Acknowledgements of devices removed from their map (or online again while the API was down)."""
    vivos = {i for (i,) in db.query(models.Equipamento.id).filter(models.Equipamento.status == "offline").all()}
    apagados = 0
    for r in db.query(models.Reconhecimento).all():
        if r.equipamento_id not in vivos:
            db.delete(r)
            apagados += 1
    db.commit()
    return apagados


def reconhecimentos(db, projeto_id=None):
    q = db.query(models.Reconhecimento)
    if projeto_id is not None:
        q = q.filter(models.Reconhecimento.projeto_id == projeto_id)
    return {r.equipamento_id: r for r in q.all()}


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
