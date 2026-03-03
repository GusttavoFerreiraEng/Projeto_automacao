from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from . import models, schemas
from .database import engine, SessionLocal
from .celery_worker import tarefa_raspar_site

# Cria as tabelas no banco se elas não existirem
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="API de Automação")

# --- 1. A PONTE COM O BANCO DE DADOS ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ROTA RAIZ ---
@app.get("/")
def home():
    return {
        "status": "OK", 
        "mensagem": "Motor de automacao rodando",
        "banco_de_dados": "OK"
    }

@app.post("/tarefas/", response_model=schemas.TarefaResponse)
def criar_tarefa(tarefa: schemas.TarefaCreate, db: Session = Depends(get_db)):
    # 1. Prepara a informação para o banco
    nova_tarefa = models.TarefaAutomacao(site_alvo=tarefa.site_alvo)
    
    # 2. Salva no PostgreSQL
    db.add(nova_tarefa)
    db.commit()
    db.refresh(nova_tarefa)
    
    # 3.Passando o ID da tarefa
    tarefa_raspar_site.delay(nova_tarefa.id)
    
    return nova_tarefa

# --- ROTA PARA LISTAR TAREFAS ---
@app.get("/tarefas/", response_model=list[schemas.TarefaResponse])
def listar_tarefas(db: Session = Depends(get_db)):
    # 1. Pede para o banco listar tudo que tem na tabela
    tarefas = db.query(models.TarefaAutomacao).all()
    return tarefas