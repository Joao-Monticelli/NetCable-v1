"""Incidents posted by the team on the public status page, with their timeline of updates."""

import json
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auditoria, crud, models
from ..nucleo import get_current_user, get_db, iso_utc, requer_editor
from ..relogio import utcnow
from .mapas import _cache_status

router = APIRouter()

# Resolved incidents stay on the public page for this long (people check "what happened yesterday?").
DIAS_RESOLVIDOS_NA_PAGINA = 7


class IncidenteIn(BaseModel):
    titulo: str
    mensagem: str
    impacto: str = "parcial"
    estado: str = "investigando"
    afetados: List[str] = []


class IncidenteUpdate(BaseModel):
    titulo: Optional[str] = None
    impacto: Optional[str] = None
    afetados: Optional[List[str]] = None


class AtualizacaoIn(BaseModel):
    estado: str
    mensagem: str


def _texto(valor, maximo, erro):
    valor = (valor or "").strip()
    if not valor:
        raise HTTPException(status_code=400, detail=erro)
    return valor[:maximo]


def _validar(impacto=None, estado=None):
    if impacto is not None and impacto not in models.IMPACTOS:
        raise HTTPException(status_code=400, detail="Impacto inválido.")
    if estado is not None and estado not in models.ESTADOS_INCIDENTE:
        raise HTTPException(status_code=400, detail="Situação inválida.")


def _afetados(db: Session, projeto_id: int, ids):
    """Keeps only ids of devices on this map (the list is shown on a public page)."""
    validos = {eq_id for (eq_id,) in db.query(models.Equipamento.id).filter(models.Equipamento.projeto_id == projeto_id)}
    return [i for i in dict.fromkeys(ids or []) if i in validos]


def ler_afetados(incidente):
    try:
        return [i for i in json.loads(incidente.afetados or "[]") if isinstance(i, str)]
    except ValueError:
        return []


def incidente_publico(incidente, nomes, interno=False):
    """`nomes`: {equipment id: name} of the devices that may be shown. `interno` adds who posted."""
    dados = {
        "id": incidente.id, "titulo": incidente.titulo, "impacto": incidente.impacto, "estado": incidente.estado,
        "criado_em": iso_utc(incidente.criado_em), "resolvido_em": iso_utc(incidente.resolvido_em),
        "afetados": [nomes[i] for i in ler_afetados(incidente) if i in nomes],
        "atualizacoes": [
            {"estado": a.estado, "mensagem": a.mensagem, "criado_em": iso_utc(a.criado_em), **({"usuario": a.usuario} if interno else {})}
            for a in reversed(incidente.atualizacoes)  # newest first, as on any status page
        ],
    }
    if interno:
        dados["afetados_ids"] = ler_afetados(incidente)
        dados["usuario"] = incidente.usuario
    return dados


def incidentes_da_pagina(db: Session, projeto_id: int, nomes, agora=None):
    """Open incidents and the ones resolved in the last DIAS_RESOLVIDOS_NA_PAGINA days, newest first."""
    agora = agora or utcnow()
    limite = agora - timedelta(days=DIAS_RESOLVIDOS_NA_PAGINA)
    q = (db.query(models.Incidente).filter(models.Incidente.projeto_id == projeto_id)
         .filter((models.Incidente.resolvido_em.is_(None)) | (models.Incidente.resolvido_em >= limite))
         .order_by(models.Incidente.criado_em.desc()))
    return [incidente_publico(i, nomes) for i in q.all()]


def _projeto(db: Session, projeto_id: int):
    projeto = crud.get_projeto(db, projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Mapa não encontrado")
    return projeto


def _incidente(db: Session, projeto_id: int, incidente_id: int):
    incidente = db.get(models.Incidente, incidente_id)
    if not incidente or incidente.projeto_id != projeto_id:
        raise HTTPException(status_code=404, detail="Incidente não encontrado")
    return incidente


def _nomes(projeto):
    return {e.id: e.nome for e in projeto.equipamentos}


@router.get("/api/projetos/{projeto_id}/incidentes")
def listar_incidentes(projeto_id: int, dias: int = 90, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    projeto = _projeto(db, projeto_id)
    limite = utcnow() - timedelta(days=max(1, min(dias, 3650)))
    q = (db.query(models.Incidente).filter(models.Incidente.projeto_id == projeto_id)
         .filter((models.Incidente.resolvido_em.is_(None)) | (models.Incidente.criado_em >= limite))
         .order_by(models.Incidente.criado_em.desc()))
    return [incidente_publico(i, _nomes(projeto), interno=True) for i in q.limit(200).all()]


@router.post("/api/projetos/{projeto_id}/incidentes")
def criar_incidente(projeto_id: int, dados: IncidenteIn, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    projeto = _projeto(db, projeto_id)
    _validar(dados.impacto, dados.estado)
    titulo = _texto(dados.titulo, 120, "Dê um título ao incidente.")
    mensagem = _texto(dados.mensagem, 2000, "Escreva o que está acontecendo.")
    agora = utcnow()
    incidente = models.Incidente(
        projeto_id=projeto_id, titulo=titulo, impacto=dados.impacto, estado=dados.estado, usuario=user.username,
        afetados=json.dumps(_afetados(db, projeto_id, dados.afetados)), criado_em=agora,
        resolvido_em=agora if dados.estado == "resolvido" else None,
    )
    incidente.atualizacoes.append(models.IncidenteAtualizacao(estado=dados.estado, mensagem=mensagem, usuario=user.username, criado_em=agora))
    db.add(incidente)
    db.commit()
    _cache_status.clear()
    auditoria.registrar(db, user, "incidente.criado", titulo, request, projeto_id=projeto_id)
    return incidente_publico(incidente, _nomes(projeto), interno=True)


@router.put("/api/projetos/{projeto_id}/incidentes/{incidente_id}")
def editar_incidente(projeto_id: int, incidente_id: int, dados: IncidenteUpdate, request: Request, db: Session = Depends(get_db),
                     user: models.Usuario = Depends(requer_editor)):
    projeto = _projeto(db, projeto_id)
    incidente = _incidente(db, projeto_id, incidente_id)
    _validar(dados.impacto)
    if dados.titulo is not None:
        incidente.titulo = _texto(dados.titulo, 120, "Dê um título ao incidente.")
    if dados.impacto is not None:
        incidente.impacto = dados.impacto
    if dados.afetados is not None:
        incidente.afetados = json.dumps(_afetados(db, projeto_id, dados.afetados))
    db.commit()
    _cache_status.clear()
    auditoria.registrar(db, user, "incidente.editado", incidente.titulo, request, projeto_id=projeto_id)
    return incidente_publico(incidente, _nomes(projeto), interno=True)


@router.post("/api/projetos/{projeto_id}/incidentes/{incidente_id}/atualizacoes")
def atualizar_incidente(projeto_id: int, incidente_id: int, dados: AtualizacaoIn, request: Request, db: Session = Depends(get_db),
                        user: models.Usuario = Depends(requer_editor)):
    projeto = _projeto(db, projeto_id)
    incidente = _incidente(db, projeto_id, incidente_id)
    _validar(estado=dados.estado)
    mensagem = _texto(dados.mensagem, 2000, "Escreva a atualização.")
    agora = utcnow()
    incidente.atualizacoes.append(models.IncidenteAtualizacao(estado=dados.estado, mensagem=mensagem, usuario=user.username, criado_em=agora))
    incidente.estado = dados.estado
    incidente.resolvido_em = (incidente.resolvido_em or agora) if dados.estado == "resolvido" else None
    db.commit()
    _cache_status.clear()
    auditoria.registrar(db, user, "incidente.atualizado", f"{incidente.titulo}: {dados.estado}", request, projeto_id=projeto_id)
    return incidente_publico(incidente, _nomes(projeto), interno=True)


@router.delete("/api/projetos/{projeto_id}/incidentes/{incidente_id}")
def excluir_incidente(projeto_id: int, incidente_id: int, request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(requer_editor)):
    _projeto(db, projeto_id)
    incidente = _incidente(db, projeto_id, incidente_id)
    titulo = incidente.titulo
    db.delete(incidente)
    db.commit()
    _cache_status.clear()
    auditoria.registrar(db, user, "incidente.excluido", titulo, request, projeto_id=projeto_id)
    return {"status": "ok"}
