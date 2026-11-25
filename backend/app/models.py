from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from datetime import datetime
from sqlalchemy.orm import relationship
from .database import Base

# Papéis da equipe: admin (tudo + usuários/sistema), editor (edita mapas), visualizador (só vê).
PAPEIS = ("admin", "editor", "visualizador")


class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    email = Column(String, nullable=True)
    papel = Column(String, default="editor", nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    # Preferências de notificação por e-mail
    receber_alertas = Column(Boolean, default=False, nullable=False)
    relatorio_diario = Column(Boolean, default=False, nullable=False)
    relatorio_horario = Column(String, default="08:00", nullable=False)  # HH:MM no fuso do sistema
    ultimo_relatorio = Column(String, nullable=True)  # data (AAAA-MM-DD) do último relatório enviado
    idioma = Column(String, default="en", nullable=False)  # idioma da interface/e-mails: en ou pt
    # Two-factor authentication (app/totp.py). The secret is Fernet-encrypted; it is set while
    # enrolling (totp_ativo still False) and only enforced after the first valid code.
    totp_segredo = Column(String, nullable=True)
    totp_ativo = Column(Boolean, default=False, nullable=False)
    totp_ultimo_passo = Column(Integer, nullable=True)  # last accepted time step (no code reuse)
    totp_recuperacao = Column(String, nullable=True)    # JSON list of SHA-256 hashes of recovery codes
    projetos = relationship("Projeto", back_populates="usuario")


class Projeto(Base):
    __tablename__ = "projetos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)  # quem criou
    # Token aleatório do link público; None = compartilhamento desativado.
    share_token = Column(String, nullable=True, unique=True, index=True)
    # Token of the public status page (separate from the map link: shows no IPs or topology).
    status_token = Column(String, nullable=True, unique=True, index=True)
    usuario = relationship("Usuario", back_populates="projetos")
    equipamentos = relationship("Equipamento", back_populates="projeto")


class Equipamento(Base):
    __tablename__ = "equipamentos"
    id = Column(String, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id"))
    nome = Column(String, index=True)
    ip = Column(String)
    tipo = Column(String)
    status = Column(String, default="offline")
    ping_time = Column(Float, nullable=True)
    pos_x = Column(Float)
    pos_y = Column(Float)
    width = Column(Float, default=200)
    height = Column(Float, default=80)
    monitor_mode = Column(String, default="ip")
    monitor_config = Column(String, nullable=True)
    # Envia alertas (e-mail/Telegram/webhook) quando este equipamento cai ou volta.
    notificar = Column(Boolean, default=True, nullable=False)
    # Racks: um rack é um equipamento com tipo "Rack" (altura_u = tamanho do rack).
    # Equipamentos montados apontam para o rack em rack_id, ocupando de rack_u
    # (U mais baixo, contando de baixo para cima como nos racks reais) até rack_u + altura_u - 1.
    rack_id = Column(String, nullable=True, index=True)
    rack_u = Column(Integer, nullable=True)
    altura_u = Column(Integer, nullable=True)
    # Modelo da biblioteca (define portas RJ45/SFP e altura desenhadas na frente).
    modelo_id = Column(Integer, ForeignKey("modelos_equipamento.id"), nullable=True)
    # Uplink: equipamento do qual este depende para ser alcançado (ex.: o switch onde está ligado).
    # Se o uplink cair, este fica "inalcançável" e não gera alerta próprio.
    depende_de = Column(String, nullable=True)
    # Atalho para outro mapa (tipo "Atalho de mapa"): mostra o resumo do mapa de destino e abre ele ao clicar.
    mapa_destino_id = Column(Integer, nullable=True)
    # Listed on the public status page of the map.
    status_publico = Column(Boolean, default=True, nullable=False)
    projeto = relationship("Projeto", back_populates="equipamentos")


class Manutencao(Base):
    """Janela de manutenção: silencia alertas de um equipamento (ou do projeto inteiro).
    - imediata: `inicio` vazio, vale até `ate` (UTC);
    - agendada: de `inicio` até `ate` (UTC);
    - recorrente: `recorrencia` = JSON {"dias": [0-6, segunda=0], "hora": "HH:MM", "minutos": N} no fuso
      do sistema; `ate` é até quando a regra vale."""
    __tablename__ = "manutencoes"
    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id"), index=True, nullable=False)
    equipamento_id = Column(String, nullable=True, index=True)  # None = projeto inteiro
    ate = Column(DateTime, nullable=False, index=True)
    inicio = Column(DateTime, nullable=True)
    recorrencia = Column(String, nullable=True)
    motivo = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class Conexao(Base):
    __tablename__ = "conexoes"
    id = Column(String, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id"))
    source = Column(String)
    target = Column(String)
    label = Column(String, nullable=True)
    source_handle = Column(String, nullable=True)
    target_handle = Column(String, nullable=True)


class HistoricoStatus(Base):
    __tablename__ = "historico_status"
    id = Column(Integer, primary_key=True, index=True)
    equipamento_id = Column(String, ForeignKey("equipamentos.id"), index=True)
    status = Column(String, nullable=False)
    tempo_ms = Column(Float, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow, index=True)


class MetricaSnmp(Base):
    """Histórico das métricas SNMP de um equipamento (uma linha por coleta)."""
    __tablename__ = "metricas_snmp"
    id = Column(Integer, primary_key=True, index=True)
    equipamento_id = Column(String, index=True, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, index=True)
    cpu_pct = Column(Float, nullable=True)
    memoria_pct = Column(Float, nullable=True)
    temperatura_c = Column(Float, nullable=True)
    in_bps = Column(Float, nullable=True)   # soma das portas físicas
    out_bps = Column(Float, nullable=True)


class ModeloEquipamento(Base):
    """Biblioteca de modelos da equipe (ex.: "Grandstream GWN7003": firewall 1U, 4 RJ45 + 2 SFP)."""
    __tablename__ = "modelos_equipamento"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, nullable=False)
    fabricante = Column(String, nullable=True)
    tipo = Column(String, nullable=False)
    altura_u = Column(Integer, default=1, nullable=False)
    portas_rj45 = Column(Integer, default=0, nullable=False)
    portas_sfp = Column(Integer, default=0, nullable=False)
    prefixo_porta = Column(String, default="", nullable=False)  # ex.: "eth" -> eth1, eth2...


class Reconhecimento(Base):
    """Someone acknowledged an offline device ("I'm on it"). Kept apart from `equipamentos`
    (rewritten on every map save); removed when the device comes back online."""
    __tablename__ = "reconhecimentos"
    equipamento_id = Column(String, primary_key=True)
    projeto_id = Column(Integer, index=True, nullable=False)
    usuario = Column(String, nullable=False)
    nota = Column(String, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class Auditoria(Base):
    """Audit log entry (see app/auditoria.py)."""
    __tablename__ = "auditoria"
    id = Column(Integer, primary_key=True, index=True)
    criado_em = Column(DateTime, default=datetime.utcnow, index=True)
    usuario = Column(String, nullable=True, index=True)  # username at the time (kept if the user is deleted)
    acao = Column(String, nullable=False, index=True)    # e.g. login.ok, usuario.criado, mapa.salvo
    detalhe = Column(String, nullable=True)
    ip = Column(String, nullable=True)
    projeto_id = Column(Integer, nullable=True)


class Configuracao(Base):
    """Configurações do sistema em chave/valor (ex.: servidor SMTP)."""
    __tablename__ = "configuracoes"
    chave = Column(String, primary_key=True)
    valor = Column(String, nullable=True)
