from sqlalchemy import Column, Integer, String, DateTime
from .database import Base # Ponto antes de database indica a mesma pasta
from datetime import datetime

class TarefaAutomacao(Base):
    __tablename__ = "tarefas_automacao"

    id = Column(Integer, primary_key=True, index=True)
    site_alvo = Column(String, index=True, nullable=False)
    status = Column(String, default="pendente")
    criado_em = Column(DateTime, default=datetime.utcnow)