from sqlalchemy import Column, Integer, String, Float, DateTime
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
    status_viabilidade = Column(String, nullable=True) # "VIÁVEL", "CARO", ou "PREJUÍZO"
    
    # Campo extra para margem ou observações (opcional)
    analise_detalhada = Column(String, nullable=True)