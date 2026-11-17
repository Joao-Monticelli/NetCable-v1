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
    projetos = relationship("Projeto", back_populates="usuario")


class Projeto(Base):
    __tablename__ = "projetos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)  # quem criou
    # Token aleatório do link público; None = compartilhamento desativado.
    share_token = Column(String, nullable=True, unique=True, index=True)
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
    projeto = relationship("Projeto", back_populates="equipamentos")


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


class Configuracao(Base):
    """Configurações do sistema em chave/valor (ex.: servidor SMTP)."""
    __tablename__ = "configuracoes"
    chave = Column(String, primary_key=True)
    valor = Column(String, nullable=True)
