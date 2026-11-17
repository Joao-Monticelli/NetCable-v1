from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import alerts, crud, models


def _sessao():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mapa(session):
    user = crud.criar_usuario(session, "owner", "hash")
    project = crud.criar_projeto(session, "Rack", user.id)
    for eq_id, status, mode in [("sw", "online", "ip"), ("fw", "offline", "ip"), ("pp", "visual", "visual")]:
        session.add(models.Equipamento(
            id=eq_id, projeto_id=project.id, nome=eq_id.upper(), ip="10.0.0.1",
            tipo="Switch", status=status, monitor_mode=mode, pos_x=0, pos_y=0, width=200, height=80,
        ))
    session.commit()
    return user, project


def _historico(session, eq_id, status, momento, tempo_ms=None):
    session.add(models.HistoricoStatus(equipamento_id=eq_id, status=status, tempo_ms=tempo_ms, criado_em=momento))
    session.commit()


def test_disponibilidade_ponderada_pelo_tempo():
    session = _sessao()
    user, project = _mapa(session)
    agora = datetime(2026, 11, 17, 12, 0, 0)
    # Online antes da janela; cai às 06h, volta às 12h-3h=09h -> 3h offline em 24h.
    _historico(session, "sw", "online", agora - timedelta(hours=30), 2.0)
    _historico(session, "sw", "offline", agora - timedelta(hours=6))
    _historico(session, "sw", "online", agora - timedelta(hours=3), 4.0)

    dados = {d["equipamento_id"]: d for d in crud.calcular_disponibilidade(session, project.id, 24, agora)}

    assert "pp" not in dados  # equipamentos somente visuais não entram no cálculo
    assert dados["sw"]["uptime_pct"] == 87.5
    assert dados["sw"]["quedas"] == 1
    assert dados["sw"]["latencia_media_ms"] == 4.0
    assert dados["fw"]["uptime_pct"] is None  # sem histórico ainda
    assert crud.calcular_disponibilidade(session, 999, 24, agora) is None


def test_resumo_projetos_conta_status():
    session = _sessao()
    user, project = _mapa(session)
    crud.definir_share_token(session, project.id, "tok")
    [resumo] = crud.resumo_projetos(session)
    assert resumo == {"id": project.id, "nome": "Rack", "compartilhado": True, "criado_por": "owner", "online": 1, "offline": 1, "visual": 1}


def test_limpeza_e_exclusao_de_projeto_removem_historico():
    session = _sessao()
    user, project = _mapa(session)
    _historico(session, "sw", "online", datetime.utcnow() - timedelta(days=40))
    _historico(session, "sw", "online", datetime.utcnow())
    assert crud.limpar_historico(session, 30) == 1
    assert session.query(models.HistoricoStatus).count() == 1

    crud.deletar_projeto(session, project.id)
    assert session.query(models.HistoricoStatus).count() == 0


def test_salvar_mapa_preserva_status_do_monitor():
    session = _sessao()
    user, project = _mapa(session)
    base = dict(nome="SW", tipo="Switch", posX=0, posY=0, width=200, height=80, monitorMode="ip", monitorConfig=None)
    crud.salvar_mapa(session, project.id, [
        {**base, "id": "sw", "ip": "10.0.0.1", "status": "offline", "pingTime": None},  # navegador desatualizado
        {**base, "id": "fw", "ip": "10.0.0.99", "status": "online", "pingTime": 1.0},   # IP mudou: aceita o enviado
    ], [])
    session.expire_all()
    assert session.get(models.Equipamento, "sw").status == "online"
    assert session.get(models.Equipamento, "fw").status == "online"


def test_mensagem_de_alerta():
    eq = SimpleNamespace(id="sw", projeto_id=1, nome="Core SW", ip="10.0.0.1")
    queda = alerts.montar_evento(eq, "Rack", "offline", "online")
    volta = alerts.montar_evento(eq, "Rack", "online", "offline", 3.2)
    assert queda["evento"] == "equipamento_offline"
    assert volta["evento"] == "equipamento_online"
    assert "OFFLINE" in alerts.formatar_mensagem(queda) and "Mapa: Rack" in alerts.formatar_mensagem(queda)
    assert "3.2 ms" in alerts.formatar_mensagem(volta)


def test_ping_paralelo_e_rapido(monkeypatch):
    import time as _t
    from app import main
    # Todas as sondas falham devagar: o resultado deve sair em ~1 timeout, não na soma deles.
    monkeypatch.setattr(main, "_sonda_tcp", lambda ip, porta: (_t.sleep(0.3), None)[1])
    monkeypatch.setattr(main, "_sonda_icmp", lambda ip: (_t.sleep(0.3), None)[1])
    inicio = _t.perf_counter()
    assert main.ping_equipamento("10.255.255.1")["status"] == "offline"
    assert _t.perf_counter() - inicio < 0.9  # sequencial levaria 1.2 s

    # Basta uma sonda responder (aqui só a porta 443).
    monkeypatch.setattr(main, "_sonda_tcp", lambda ip, porta: 4.2 if porta == 443 else None)
    assert main.ping_equipamento("10.0.0.1") == {"ip": "10.0.0.1", "status": "online", "tempo_ms": 4.2}


def test_icmp_com_erro_nao_conta_como_online(monkeypatch):
    from app import main
    monkeypatch.setattr(main.ping3, "ping", lambda ip, timeout: False)  # ping3 devolve False em erro
    assert main._sonda_icmp("10.0.0.1") is None
