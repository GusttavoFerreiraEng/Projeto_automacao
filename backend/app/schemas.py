from pydantic import BaseModel, ConfigDict
from datetime import datetime

# 1. Esquema para CRIAR uma tarefa (o que o usuário envia na API)
class TarefaCreate(BaseModel):
    site_alvo: str

# 2. Esquema para LER uma tarefa (o que a API devolve para o usuário)
class TarefaResponse(BaseModel):
    id: int
    site_alvo: str
    status: str
    criado_em: datetime

    # Permite ler os dados do SQLAlchemy
    model_config = ConfigDict(from_attributes=True)