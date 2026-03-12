from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class TarefaAutomacao(Base):
    __tablename__ = "tarefas_automacao"

    id = Column(Integer, primary_key=True, index=True)
    site = Column(String, index=True, nullable=False)
    status = Column(String, default="PENDENTE")
    criado_em = Column(DateTime, default=datetime.utcnow)

    preco_venda = Column(Float, nullable=True)      
    preco_custo = Column(Float, nullable=True)      
    orcamento_maximo = Column("orc_maximo", Float, nullable=True) 
    status_viabilidade = Column(String, nullable=True)
    
    analise_detalhada = Column(String, nullable=True)
    link_produto = Column(String, nullable=True)

    # Relacionamento: uma tarefa tem muitos registros de histórico
    historicos = relationship("HistoricoPreco", back_populates="tarefa", cascade="all, delete-orphan")

class HistoricoPreco(Base):
    __tablename__ = "historico_precos"

    id = Column(Integer, primary_key=True, index=True)
    # Chave estrangeira ligando ao ID da tarefa
    tarefa_id = Column(Integer, ForeignKey("tarefas_automacao.id"), nullable=False)
    
    preco_venda = Column(Float, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # Relacionamento inverso
    tarefa = relationship("TarefaAutomacao", back_populates="historicos")