import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator


class TarefaCreate(BaseModel):
    site: str
    preco_custo: Optional[float] = 0.0
    orcamento: Optional[float] = None

    @field_validator("preco_custo", "orcamento", mode="before")
    @classmethod
    def limpar_moeda(cls, v):
        if v is None:
            return v
        if isinstance(v, (int, float)):
            return float(v)
        apenas_numeros = re.sub(r"[^\d,.]", "", str(v))
        if not apenas_numeros:
            return 0.0
        if "," in apenas_numeros and "." in apenas_numeros:
            apenas_numeros = apenas_numeros.replace(".", "").replace(",", ".")
        elif "," in apenas_numeros:
            apenas_numeros = apenas_numeros.replace(",", ".")
        try:
            return float(apenas_numeros)
        except ValueError:
            return 0.0


class HistoricoPrecoSchema(BaseModel):
    id: int
    preco_venda: float
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class TarefaResponse(BaseModel):
    id: int
    site: str
    status: str
    preco_custo: float
    orcamento: Optional[float] = None
    preco_venda: Optional[float] = None
    status_viabilidade: Optional[str] = None
    link_produto: Optional[str] = None
    analise: Optional[str] = None
    criado_em: datetime
    historicos: List[HistoricoPrecoSchema] = []

    model_config = ConfigDict(from_attributes=True)


class TarefaAceitaResponse(BaseModel):
    """Retornado no POST — informa que a tarefa foi aceita e está sendo processada."""
    id: int
    status: str
    mensagem: str