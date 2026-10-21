from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Projeto(Base):
    __tablename__ = "projetos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
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
    projeto = relationship("Projeto", back_populates="equipamentos")

class Conexao(Base):
    __tablename__ = "conexoes"
    id = Column(String, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id"))
    source = Column(String)
    target = Column(String)
    label = Column(String, nullable=True)
    # NOVAS COLUNAS
    source_handle = Column(String, nullable=True) 
    target_handle = Column(String, nullable=True)