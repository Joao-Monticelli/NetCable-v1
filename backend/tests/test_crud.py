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


def test_validacao_de_racks():
    rack = {"id": "r1", "nome": "Rack 12U", "tipo": "Rack", "alturaU": 12}
    sw = {"id": "sw", "nome": "Switch", "tipo": "Switch", "rackId": "r1", "rackU": 11, "alturaU": 1}
    srv = {"id": "srv", "nome": "Servidor", "tipo": "Servidor", "rackId": "r1", "rackU": 1, "alturaU": 2}
    assert crud.validar_racks([rack, sw, srv]) is None
    assert "não cabe" in crud.validar_racks([rack, {**sw, "rackU": 12, "alturaU": 2}])           # passa do topo
    assert "mesmo U2" in crud.validar_racks([rack, srv, {**sw, "rackU": 2}])                      # sobreposição
    assert "não existe" in crud.validar_racks([{**sw, "rackId": "fantasma"}])
    assert "tamanho inválido" in crud.validar_racks([{**rack, "alturaU": 0}])


def test_salvar_mapa_guarda_posicao_no_rack():
    session = _sessao()
    try:
        projeto = crud.criar_projeto(session, "Homelab")
        base = dict(posX=0, posY=0, width=200, height=80, status="visual", monitorMode="visual", monitorConfig=None)
        crud.salvar_mapa(session, projeto.id, [
            {**base, "id": "r1", "nome": "Rack", "ip": "Sem IP", "tipo": "Rack", "alturaU": 12},
            {**base, "id": "sw", "nome": "Switch", "ip": "10.0.0.2", "tipo": "Switch", "status": "offline", "monitorMode": "ip", "rackId": "r1", "rackU": 12, "alturaU": 1},
        ], [])
        session.expire_all()
        sw = session.get(models.Equipamento, "sw")
        assert (sw.rack_id, sw.rack_u, sw.altura_u) == ("r1", 12, 1)
        assert session.get(models.Equipamento, "r1").altura_u == 12
        [resumo] = crud.resumo_projetos(session)
        assert resumo["visual"] == 0 and resumo["offline"] == 1  # o rack não conta como equipamento
    finally:
        session.close()
