from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import crud, models


def test_projects_are_isolated_by_user():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        first = crud.criar_usuario(session, "first", "hash")
        second = crud.criar_usuario(session, "second", "hash")
        crud.criar_projeto(session, "Mapa privado", first.id)

        assert [project.nome for project in crud.get_projetos(session, first.id)] == ["Mapa privado"]
        assert crud.get_projetos(session, second.id) == []
    finally:
        session.close()


def test_status_history_is_scoped_to_project_owner():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        user = crud.criar_usuario(session, "owner", "hash")
        other = crud.criar_usuario(session, "other", "hash")
        project = crud.criar_projeto(session, "Mapa", user.id)
        equipment = models.Equipamento(
            id="node-1", projeto_id=project.id, nome="Router", ip="127.0.0.1",
            tipo="Roteador", status="online", pos_x=0, pos_y=0, width=200, height=80,
        )
        session.add(equipment)
        session.commit()
        crud.registrar_status(session, equipment.id, "online", 1.2)

        assert len(crud.get_historico(session, project.id, user.id)) == 1
        assert crud.get_historico(session, project.id, other.id) is None
    finally:
        session.close()


def _sessao():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_monitoring_updates_current_equipment_status():
    session = _sessao()
    try:
        user = crud.criar_usuario(session, "owner", "hash")
        project = crud.criar_projeto(session, "Mapa", user.id)
        session.add(models.Equipamento(
            id="node-1", projeto_id=project.id, nome="Switch", ip="10.0.0.1",
            tipo="Switch", status="online", pos_x=0, pos_y=0, width=200, height=80,
        ))
        session.commit()

        crud.atualizar_status_equipamento(session, "node-1", "online", 3.0)
        crud.registrar_status(session, "node-1", "online", 3.0)
        # Mesmo status em menos de 60s: não grava histórico, mas o status atual deve persistir.
        crud.atualizar_status_equipamento(session, "node-1", "online", 7.5)
        crud.registrar_status(session, "node-1", "online", 7.5)
        session.expire_all()

        equipamento = session.get(models.Equipamento, "node-1")
        assert equipamento.ping_time == 7.5
        assert len(crud.get_historico(session, project.id, user.id)) == 1

        crud.atualizar_status_equipamento(session, "node-1", "offline", None)
        _, mudou, anterior = crud.registrar_status(session, "node-1", "offline", None)
        session.expire_all()
        assert session.get(models.Equipamento, "node-1").status == "offline"
        assert mudou and anterior == "online"
    finally:
        session.close()


def test_share_token_is_owner_scoped_and_revocable():
    session = _sessao()
    try:
        owner = crud.criar_usuario(session, "owner", "hash")
        other = crud.criar_usuario(session, "other", "hash")
        project = crud.criar_projeto(session, "Mapa", owner.id)

        assert crud.get_projeto_por_token(session, None) is None
        assert crud.definir_share_token(session, project.id, other.id, "abc") is None
        crud.definir_share_token(session, project.id, owner.id, "abc")
        assert crud.get_projeto_por_token(session, "abc").id == project.id

        crud.definir_share_token(session, project.id, owner.id, None)
        assert crud.get_projeto_por_token(session, "abc") is None
    finally:
        session.close()
