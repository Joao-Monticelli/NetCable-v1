from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import crud, email_service, models


def _sessao():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


class _SMTPFalso:
    instancias = []

    def __init__(self, host, porta, timeout=None, context=None):
        self.host, self.porta, self.acoes = host, porta, []
        _SMTPFalso.instancias.append(self)

    def starttls(self, context=None):
        self.acoes.append("starttls")

    def login(self, usuario, senha):
        self.acoes.append(("login", usuario, senha))

    def send_message(self, msg):
        self.acoes.append(("send", msg["To"], msg["Subject"]))

    def quit(self):
        self.acoes.append("quit")


def test_enviar_email_starttls_e_login(monkeypatch):
    monkeypatch.setattr(email_service.smtplib, "SMTP", _SMTPFalso)
    cfg = {"host": "smtp.exemplo.com", "porta": "587", "seguranca": "starttls", "usuario": "noc", "senha": "x", "remetente": "noc@exemplo.com"}
    email_service.enviar_email(cfg, ["a@exemplo.com", "", "b@exemplo.com"], "Assunto", "corpo", "<b>corpo</b>")
    smtp = _SMTPFalso.instancias[-1]
    assert (smtp.host, smtp.porta) == ("smtp.exemplo.com", 587)
    assert smtp.acoes == ["starttls", ("login", "noc", "x"), ("send", "a@exemplo.com, b@exemplo.com", "Assunto"), "quit"]


def test_enviar_email_sem_configuracao():
    try:
        email_service.enviar_email({}, ["a@exemplo.com"], "x", "y")
        assert False, "deveria falhar"
    except RuntimeError as exc:
        assert "SMTP" in str(exc)


def test_email_de_alerta_agrupa_eventos():
    eventos = [
        {"status": "offline", "equipamento": "Core SW", "ip": "10.0.0.1", "projeto": "Rack A"},
        {"status": "offline", "equipamento": "Firewall", "ip": "10.0.0.254", "projeto": "Rack A"},
        {"status": "online", "equipamento": "AP Sala", "ip": "10.0.0.30", "projeto": "Rack B", "tempo_ms": 2.1},
    ]
    assunto, texto, html = email_service.montar_email_alerta(eventos)
    assert assunto == "[NetCable] 2 equipamento(s) offline, 1 recuperado(s)"
    assert "Core SW" in texto and "Firewall" in html and "2.1 ms" in texto


def test_relatorio_diario():
    session = _sessao()
    projeto = crud.criar_projeto(session, "Rack A")
    session.add(models.Equipamento(id="sw", projeto_id=projeto.id, nome="Core SW", ip="10.0.0.1", tipo="Switch",
                                   status="online", pos_x=0, pos_y=0, width=200, height=80))
    session.add(models.Equipamento(id="pp", projeto_id=projeto.id, nome="Patch", ip="Sem IP", tipo="PC",
                                   status="visual", monitor_mode="visual", pos_x=0, pos_y=0, width=200, height=80))
    agora = datetime(2026, 11, 17, 8, 0, 0)
    for horas, status, ms in [(30, "online", 1.0), (6, "offline", None), (5, "online", 3.0)]:
        session.add(models.HistoricoStatus(equipamento_id="sw", status=status, tempo_ms=ms, criado_em=agora - timedelta(hours=horas)))
    session.commit()

    relatorio = crud.montar_relatorio(session, 24, agora)
    [mapa] = relatorio["mapas"]
    [eq] = mapa["equipamentos"]  # o equipamento só visual fica de fora
    assert eq["quedas"] == 1 and [m["para"] for m in eq["mudancas"]] == ["offline", "online"]

    assunto, texto, html = email_service.montar_email_relatorio(relatorio, lambda d: d.strftime("%H:%M"))
    assert assunto == "[NetCable] Relatório diário — 1 queda(s), 0 offline agora"
    assert "Core SW" in texto and "02:00  Core SW -> offline" in texto and "Rack A" in html


def test_salvar_mapa_guarda_opcao_de_notificar():
    session = _sessao()
    projeto = crud.criar_projeto(session, "Mapa")
    base = dict(tipo="PC", posX=0, posY=0, width=200, height=80, status="offline", monitorConfig=None)
    crud.salvar_mapa(session, projeto.id, [
        {**base, "id": "a", "nome": "Impressora", "ip": "10.0.0.9", "notificar": False},
        {**base, "id": "b", "nome": "Servidor", "ip": "10.0.0.10"},
    ], [])
    session.expire_all()
    assert session.get(models.Equipamento, "a").notificar is False
    assert session.get(models.Equipamento, "b").notificar is True
