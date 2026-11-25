from app.relogio import utcnow
from datetime import timedelta
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import alerts, crud, email_service, models, regras_alerta


def _sessao():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _rede(session):
    """firewall <- switch <- (ap, nas); impressora sem uplink."""
    projeto = crud.criar_projeto(session, "Casa")
    for eq_id, pai in [("fw", None), ("sw", "fw"), ("ap", "sw"), ("nas", "sw"), ("imp", None)]:
        session.add(models.Equipamento(id=eq_id, projeto_id=projeto.id, nome=eq_id.upper(), ip="10.0.0.1", tipo="Switch",
                                       status="online", pos_x=0, pos_y=0, width=200, height=80, depende_de=pai))
    session.commit()
    regras_alerta._suprimidos.clear()
    return projeto


def _cair(session, projeto, ids, status="offline"):
    eventos = []
    for eq_id in ids:
        eq = crud.get_equipamento(session, eq_id)
        anterior = eq.status
        eq.status = status
        eventos.append(alerts.montar_evento(eq, projeto.nome, status, anterior))
    session.commit()
    return eventos


def test_queda_do_switch_gera_um_alerta_com_os_dependentes():
    session = _sessao()
    projeto = _rede(session)
    enviados = regras_alerta.aplicar(session, _cair(session, projeto, ["ap", "sw", "nas", "imp"]))
    assert [e["equipamento"] for e in enviados] == ["SW", "IMP"]
    assert sorted(enviados[0]["dependentes"]) == ["AP", "NAS"]
    assert "2 device(s) behind it unreachable: AP, NAS" in alerts.formatar_mensagem(enviados[0], "en")

    # O mapa mostra os inalcançáveis e a causa.
    assert regras_alerta.inalcancaveis(session.query(models.Equipamento).all()) == {"ap": "sw", "nas": "sw"}

    # Volta tudo: um alerta de recuperação do switch, com os dependentes juntos.
    enviados = regras_alerta.aplicar(session, _cair(session, projeto, ["sw", "ap", "nas"], "online"))
    assert [e["equipamento"] for e in enviados] == ["SW"]
    assert sorted(enviados[0]["dependentes"]) == ["AP", "NAS"]


def test_causa_raiz_e_a_mais_proxima_da_raiz_e_ciclos_nao_travam():
    session = _sessao()
    projeto = _rede(session)
    _cair(session, projeto, ["fw", "sw", "ap"])
    assert regras_alerta.inalcancaveis(session.query(models.Equipamento).all()) == {"sw": "fw", "ap": "fw"}
    crud.get_equipamento(session, "fw").depende_de = "ap"  # ciclo fw -> ap -> sw -> fw
    session.commit()
    regras_alerta.inalcancaveis(session.query(models.Equipamento).all())  # não entra em loop


def test_manutencao_silencia_queda_e_volta():
    session = _sessao()
    projeto = _rede(session)
    regras_alerta.criar_manutencao(session, projeto.id, utcnow() + timedelta(hours=1), equipamento_id="imp")
    assert regras_alerta.aplicar(session, _cair(session, projeto, ["imp"])) == []
    regras_alerta.cancelar_manutencao(session, projeto.id, "imp")
    # A queda foi silenciada, então a volta também não avisa.
    assert regras_alerta.aplicar(session, _cair(session, projeto, ["imp"], "online")) == []

    # Manutenção do projeto inteiro.
    regras_alerta.criar_manutencao(session, projeto.id, utcnow() + timedelta(hours=1))
    assert regras_alerta.aplicar(session, _cair(session, projeto, ["fw"])) == []
    # Janela vencida não vale mais e é limpa.
    regras_alerta.criar_manutencao(session, projeto.id, utcnow() - timedelta(minutes=1))
    assert regras_alerta.limpar_manutencoes_vencidas(session) == 1
    assert [e["equipamento"] for e in regras_alerta.aplicar(session, _cair(session, projeto, ["imp"]))] == ["IMP"]


def test_email_lista_dependentes():
    evento = {"status": "offline", "equipamento": "SW", "ip": "10.0.0.2", "projeto": "Casa", "dependentes": ["AP", "NAS"]}
    assunto, texto, html = email_service.montar_email_alerta([evento], "pt")
    assert "2 equipamento(s) atrás dele inalcançável(is): AP, NAS" in texto and "AP, NAS" in html


def test_canais_discord_e_ntfy_e_mascara_de_segredos():
    c = {"discord_url": "https://discord.com/api/webhooks/1/segredo", "ntfy_url": "https://ntfy.sh/casa", "ntfy_token": "tk_x",
         "telegram_token": "123:ABC", "telegram_chat": "9", "webhook_url": "", "idioma": "en"}
    assert alerts.canais_configurados(None, c) == {"webhook": False, "telegram": True, "discord": True, "ntfy": True, "email": False}
    evento = {"status": "offline", "equipamento": "SW", "ip": "10.0.0.2", "projeto": "Casa"}
    with mock.patch("app.alerts.requests.post") as post:
        alerts._enviar([evento], None, {}, c)
    urls = [chamada.args[0] for chamada in post.call_args_list]
    assert urls == ["https://api.telegram.org/bot123:ABC/sendMessage", c["discord_url"], c["ntfy_url"]]
    ntfy = post.call_args_list[2].kwargs
    assert ntfy["headers"]["Priority"] == "high" and ntfy["headers"]["Authorization"] == "Bearer tk_x"
    erro = Exception("Max retries exceeded with url: https://api.telegram.org/bot123:ABC/sendMessage")
    assert "123:ABC" not in alerts.erro_seguro(erro, c)
