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
