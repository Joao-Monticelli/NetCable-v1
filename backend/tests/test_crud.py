from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import crud, models


def _sessao():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_mapas_sao_da_equipe():
    """Modelo de equipe: todos os usuários enxergam os mesmos mapas."""
    session = _sessao()
    try:
        primeiro = crud.criar_usuario(session, "first", "hash")
        crud.criar_usuario(session, "second", "hash")
        crud.criar_projeto(session, "Mapa da equipe", primeiro.id)
        [resumo] = crud.resumo_projetos(session)
        assert resumo["nome"] == "Mapa da equipe"
        assert resumo["criado_por"] == "first"
    finally:
        session.close()


def test_excluir_usuario_mantem_os_mapas():
    session = _sessao()
    try:
        autor = crud.criar_usuario(session, "autor", "hash")
        projeto = crud.criar_projeto(session, "Rack A", autor.id)
        assert crud.deletar_usuario(session, autor.id)
        session.expire_all()
        assert crud.get_projeto(session, projeto.id).user_id is None
    finally:
        session.close()


def test_contagem_de_admins_ativos():
    session = _sessao()
    try:
        a1 = crud.criar_usuario(session, "a1", "hash", papel="admin")
        crud.criar_usuario(session, "ed", "hash", papel="editor")
        assert crud.contar_admins_ativos(session) == 1
        assert crud.contar_admins_ativos(session, exceto_id=a1.id) == 0
        crud.atualizar_usuario(session, a1.id, ativo=False)
        assert crud.contar_admins_ativos(session) == 0
    finally:
        session.close()


def test_configuracoes_chave_valor():
    session = _sessao()
    try:
        crud.salvar_configuracoes(session, {"smtp.host": "smtp.exemplo.com", "smtp.porta": "587", "sistema.fuso": "UTC"})
        crud.salvar_configuracoes(session, {"smtp.porta": "465"})
        assert crud.get_configuracoes(session, "smtp.") == {"smtp.host": "smtp.exemplo.com", "smtp.porta": "465"}
    finally:
        session.close()


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
        # Mesmo status logo em seguida: não grava histórico, mas o status atual deve persistir.
        crud.atualizar_status_equipamento(session, "node-1", "online", 7.5)
        crud.registrar_status(session, "node-1", "online", 7.5)
        session.expire_all()

        assert session.get(models.Equipamento, "node-1").ping_time == 7.5
        assert len(crud.get_historico(session, project.id)) == 1

        crud.atualizar_status_equipamento(session, "node-1", "offline", None)
        _, mudou, anterior = crud.registrar_status(session, "node-1", "offline", None)
        session.expire_all()
        assert session.get(models.Equipamento, "node-1").status == "offline"
        assert mudou and anterior == "online"
    finally:
        session.close()


def test_share_token_revogavel():
    session = _sessao()
    try:
        project = crud.criar_projeto(session, "Mapa")
        assert crud.get_projeto_por_token(session, None) is None
        assert crud.definir_share_token(session, 999, "abc") is None
        crud.definir_share_token(session, project.id, "abc")
        assert crud.get_projeto_por_token(session, "abc").id == project.id
        crud.definir_share_token(session, project.id, None)
        assert crud.get_projeto_por_token(session, "abc") is None
    finally:
        session.close()
