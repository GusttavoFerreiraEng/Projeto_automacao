import os
import logging
import redis

from fastapi import FastAPI, Depends, HTTPException, Security, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from .database import models, schemas
from .database.connection import engine, get_db
from .celery_worker import tarefa_raspar_site

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("api")

# Cria as tabelas na primeira inicialização
# (quando tiver Alembic, remover esta linha e usar migrations)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API Automação de Preços",
    description="MVP — rastreia preços no Mercado Livre de forma assíncrona.",
    version="1.0.0",
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

API_KEY = os.getenv("API_KEY_DINO", "dinopanquecas")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verificar_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Chave de API inválida.")
    return api_key


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"erro": True, "codigo": exc.status_code, "detalhe": exc.detail},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"erro": True, "codigo": 429, "detalhe": "Muitas requisições. Tente mais tarde."},
    )


@app.get("/Serviços", tags=["Infra"])
def check_services():
    resultado = {"status": "healthy", "servicos": {}}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        resultado["servicos"]["banco_de_dados"] = "online"
    except Exception as e:
        resultado["servicos"]["banco_de_dados"] = f"offline: {e}"
        resultado["status"] = "unhealthy"

    try:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.ping()
        resultado["servicos"]["redis"] = "online"
    except Exception as e:
        resultado["servicos"]["redis"] = f"offline: {e}"
        resultado["status"] = "unhealthy"

    return resultado


@app.get("/", tags=["Infra"])
def raiz():
    return {"status": "ok", "versao": "1.0.0"}


@app.post(
    "/tarefas/",
    response_model=schemas.TarefaAceitaResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verificar_api_key)],
    tags=["Tarefas"],
    summary="Cria uma tarefa de rastreamento de preço",
    description=(
        "Aceita a tarefa e a enfileira para processamento em background. "
        "Use GET /tarefas/{id} para consultar o resultado."
    ),
)
@limiter.limit("10/minute")
def criar_tarefa(
    request: Request,
    tarefa: schemas.TarefaCreate,
    db: Session = Depends(get_db),
):
    logger.info(f"Nova tarefa recebida — site: {tarefa.site}")

    nova_tarefa = models.TarefaAutomacao(
        site=tarefa.site,
        preco_custo=tarefa.preco_custo,
        orcamento=tarefa.orcamento,
    )
    db.add(nova_tarefa)
    db.commit()
    db.refresh(nova_tarefa)

    # Dispara o worker em background
    tarefa_raspar_site.delay(nova_tarefa.id)

    return schemas.TarefaAceitaResponse(
        id=nova_tarefa.id,
        status=nova_tarefa.status,
        mensagem=(
            f"Tarefa {nova_tarefa.id} aceita e em processamento. "
            f"Consulte GET /tarefas/{nova_tarefa.id} para acompanhar."
        ),
    )


@app.get(
    "/tarefas/",
    response_model=list[schemas.TarefaResponse],
    dependencies=[Depends(verificar_api_key)],
    tags=["Tarefas"],
    summary="Lista todas as tarefas",
)
def listar_tarefas(db: Session = Depends(get_db)):
    return db.query(models.TarefaAutomacao).order_by(
        models.TarefaAutomacao.criado_em.desc()
    ).all()


@app.get(
    "/tarefas/{tarefa_id}",
    response_model=schemas.TarefaResponse,
    dependencies=[Depends(verificar_api_key)],
    tags=["Tarefas"],
    summary="Consulta uma tarefa específica (use para fazer polling do status)",
)
def ler_tarefa(tarefa_id: int, db: Session = Depends(get_db)):
    tarefa = db.query(models.TarefaAutomacao).filter(
        models.TarefaAutomacao.id == tarefa_id
    ).first()
    if not tarefa:
        raise HTTPException(status_code=404, detail=f"Tarefa {tarefa_id} não encontrada.")
    return tarefa


@app.delete(
    "/tarefas/{tarefa_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verificar_api_key)],
    tags=["Tarefas"],
    summary="Remove uma tarefa e seu histórico de preços",
)
def deletar_tarefa(tarefa_id: int, db: Session = Depends(get_db)):
    try:
        tarefa = db.query(models.TarefaAutomacao).filter(
            models.TarefaAutomacao.id == tarefa_id
        ).first()

        if not tarefa:
            raise HTTPException(
                status_code=404,
                detail=f"Tarefa {tarefa_id} não encontrada.",
            )

        db.delete(tarefa)
        db.commit()
        return {"mensagem": f"Tarefa {tarefa_id} removida com sucesso."}

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao deletar tarefa {tarefa_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao acessar o banco de dados.",
        )