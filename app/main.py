from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from . import models, schemas
from .database import engine, SessionLocal
from .celery_worker import tarefa_raspar_site
from fastapi import HTTPException

# Cria as tabelas no banco se elas não existirem
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="API Automação")

#  A PONTE COM O BANCO DE DADOS 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ROTA RAIZ 
@app.get("/")
def home():
    return {
        "status": "OK", 
        "mensagem": "OK",
        "banco_de_dados": "OK"
    }

# ROTA PARA CRIAR TAREFAS 
@app.post("/tarefas/", response_model=schemas.TarefaResponse)
def criar_tarefa(tarefa: schemas.TarefaCreate, db: Session = Depends(get_db)):
    
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
@app.get("/tarefas/", response_model=list[schemas.TarefaResponse])
def listar_tarefas(db: Session = Depends(get_db)):
    tarefas = db.query(models.TarefaAutomacao).all()
    return tarefas

@app.get("/tarefas/{tarefa_id}", response_model=schemas.TarefaResponse)
def ler_tarefa_especifica(tarefa_id: int, db: Session = Depends(get_db)):
    # O Dino vai no banco procurar exatamente o ID que você pediu
    tarefa = db.query(models.TarefaAutomacao).filter(models.TarefaAutomacao.id == tarefa_id).first()
    
    # Se não achar, devolve um erro 404
    if not tarefa:
        raise HTTPException(status_code=404, detail="Caçada não encontrada pelo Dino!")
        
    return tarefa