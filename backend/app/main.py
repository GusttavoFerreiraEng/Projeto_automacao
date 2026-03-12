from fastapi import FastAPI, Depends, HTTPException, Security, Request
from fastapi.responses import JSONResponse
from fastapi import HTTPException, Depends, status
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
from . import models, schemas
from .database import engine, SessionLocal
from .celery_worker import tarefa_raspar_site
import redis
import logging
import os

# Carregar variáveis de ambiente
load_dotenv()

# Configuração básica de log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("DinoLogger")

# Cria as tabelas no banco se elas não existirem
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="API Automação")

# CONFIGURAÇÃO DO LIMITADOR
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

API_KEY_DINO = os.getenv("API_KEY_DINO", "dinopanquecas")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verificar_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY_DINO:
        raise HTTPException(status_code=403, detail="Acesso negado! Chave inválida.")
    return api_key

@app.exception_handler(StarletteHTTPException)
async def custom_custom_exception_handler(Request, exc):
    mensagens_dino = {
        403: "Acesso negado, meu chapa! Cadê a chave do Dino?",
        404: "Ops! O Dino caçou por todo lado e não encontrou isso.",
        405: "Método não permitido. Você tentou fazer algo que essa rota não aceita.",
        500: "Ih, deu um problema interno no servidor do Dino."
    }
    mensagem = mensagens_dino.get(exc.status_code, "Ocorreu um erro inesperado.")

    return JSONResponse(
        status_code=exc.status_code,
        content={"erro": True, "codigo": exc.status_code, "mensagem_dino": mensagem}
    )

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(Request, exc):
    return JSONResponse(
        status_code=429,
        content={"erro": True, "codigo": 429, "mensagem_dino": "Limite de requisições excedido. Tente novamente mais tarde."}
    )


@app.get("/health", tags=["Infra"])
def health_check():
    health_status = {"status": "healthy", "servico": "dino-api", "checagens": {}}

    try: 
        with engine.connect() as connection:
            from sqlalchemy import text
            connection.execute(text("SELECT 1"))
        health_status["checagens"]["banco_de_dados"] = "online"
    except Exception as e:
        health_status["checagens"]["banco_de_dados"] = f"offline: {str(e)}"
        health_status["status"] = "unhealthy"  

    try:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.ping()
        health_status["checagens"]["redis"] = "online"
    except Exception as e:
        health_status["checagens"]["redis"] = f"offline: {str(e)}"
        health_status["status"] = "unhealthy"

    return health_status


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ROTA RAIZ 
@app.get("/", tags=["Inicio"])
def home():
    return {
        "status": "OK", 
        "mensagem": "OK",
        "banco_de_dados": "OK"
    }

# ROTA PARA CRIAR TAREFAS 
@app.post("/tarefas/", response_model=schemas.TarefaResponse, dependencies=[Depends(verificar_api_key)])
@limiter.limit("5/minute")
def criar_tarefa(Request: Request, tarefa: schemas.TarefaCreate, db: Session = Depends(get_db)):
    logger.info(f"Nova Tarefa recebida site: {tarefa.site}")
    
    nova_tarefa = models.TarefaAutomacao(
        site=tarefa.site,
        preco_custo=tarefa.preco_custo, 
        
        orcamento_maximo=tarefa.orc_maximo 
    )
    
    db.add(nova_tarefa)
    db.commit()
    db.refresh(nova_tarefa)
    
    tarefa_raspar_site.delay(nova_tarefa.id)
    
    return nova_tarefa

# ROTA PARA LISTAR TAREFAS
@app.get("/tarefas/", response_model=list[schemas.TarefaResponse], dependencies=[Depends(verificar_api_key)])
def listar_tarefas(db: Session = Depends(get_db)):
    tarefas = db.query(models.TarefaAutomacao).all()
    return tarefas

@app.get("/tarefas/{tarefa_id}", response_model=schemas.TarefaResponse, dependencies=[Depends(verificar_api_key)])
def ler_tarefa_especifica(tarefa_id: int, db: Session = Depends(get_db)):
    tarefa = db.query(models.TarefaAutomacao).filter(models.TarefaAutomacao.id == tarefa_id).first()
    
    # Se não achar, devolve um erro 404
    if not tarefa:
        raise HTTPException(status_code=404, detail="Caçada não encontrada pelo Dino!")
        
    return tarefa

@app.delete("/tarefas/{tarefa_id}", status_code=status.HTTP_200_OK)
def deletar_tarefa(tarefa_id: int, db: Session = Depends(get_db)):
    try:
        # Busca a tarefa
        tarefa = db.query(models.TarefaAutomacao).filter(models.TarefaAutomacao.id == tarefa_id).first()
        
        # Tratamento de erro: ID inexistente
        if not tarefa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Tarefa com ID {tarefa_id} não encontrada no habitat do Dino."
            )
        
        # Tenta deletar
        db.delete(tarefa)
        db.commit()
        
        return {"message": f"Tarefa {tarefa_id} e seu histórico foram removidos com sucesso."}

    except SQLAlchemyError as e:
        # Tratamento de erro: Falha no Banco de Dados
        db.rollback() # Reverte qualquer alteração se der erro no commit
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao acessar o banco de dados. O Dino tropeçou!"
        )