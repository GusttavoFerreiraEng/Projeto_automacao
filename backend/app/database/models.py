from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .connection import Base
from datetime import datetime


class TarefaAutomacao(Base):
    __tablename__ = "tarefas_automacao"

    id = Column(Integer, primary_key=True, index=True)
    site = Column(String, index=True, nullable=False)
    status = Column(String, default="pendente")
    criado_em = Column(DateTime, default=datetime.utcnow)

    preco_custo = Column(Float, nullable=True, default=0.0)
    orcamento = Column(Float, nullable=True)

    preco_venda = Column(Float, nullable=True)
    status_viabilidade = Column(String, nullable=True)
    analise = Column(String, nullable=True)
    link_produto = Column(String, nullable=True)

    historicos = relationship(
        "HistoricoPreco",
        back_populates="tarefa",
        cascade="all, delete-orphan"
    )


class HistoricoPreco(Base):
    __tablename__ = "historico_precos"

    id = Column(Integer, primary_key=True, index=True)
    tarefa_id = Column(Integer, ForeignKey("tarefas_automacao.id"), nullable=False)
    preco_venda = Column(Float, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)

    tarefa = relationship("TarefaAutomacao", back_populates="historicos")