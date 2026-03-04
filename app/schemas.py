import re
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime

# 1. Esquema para CRIAR uma tarefa (o que o usuário envia na API)
class TarefaCreate(BaseModel):
    site: str
    preco_custo: Optional[float] = 0.0
    orc_maximo: Optional[float] = None

    # Validador que limpa os números ANTES do Pydantic converter para float
    @field_validator('preco_custo', 'orc_maximo', mode='before')
    @classmethod
    def limpar_moeda(cls, v):
        if v is None:
            return v  
        if isinstance(v, (int, float)):
            return float(v)
        
        apenas_numeros = re.sub(r'[^\d,.]', '', str(v))
        if not apenas_numeros:
            return 0.0
            
        if ',' in apenas_numeros and '.' in apenas_numeros:
            apenas_numeros = apenas_numeros.replace('.', '').replace(',', '.')
        elif ',' in apenas_numeros:
            apenas_numeros = apenas_numeros.replace(',', '.')
        
        try:
            return float(apenas_numeros)
        except ValueError:
            return 0.0

# 2. Esquema para LER uma tarefa (o que a API devolve para o usuário)
class TarefaResponse(BaseModel):
    id: int
    site: str
    status: str
    preco_venda: Optional[float] = None
    preco_custo: float
    orc_maximo: Optional[float] = None
    status_viabilidade: Optional[str] = None
    criado_em: datetime    

    # Permite ler os dados do SQLAlchemy
    model_config = ConfigDict(from_attributes=True)