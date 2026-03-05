import os
import re
import logging
from celery import Celery
from dotenv import load_dotenv
from .database import SessionLocal
from . import models
from .scrapers.mercadolivre import raspar_primeiro_produto

load_dotenv()

# Configuração básica de log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("DinoLogger")

# Configuração do Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker_automacao",
    broker=REDIS_URL,
    backend=REDIS_URL
)

def limpar_preco(valor):
    """Converte qualquer entrada para float puro, lidando com strings ou números."""
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    
    # Se for string (ex: capturada do HTML), limpa símbolos
    apenas_numeros = re.sub(r'[^\d,.]', '', str(valor))
    if ',' in apenas_numeros and '.' in apenas_numeros:
        apenas_numeros = apenas_numeros.replace('.', '').replace(',', '.')
    elif ',' in apenas_numeros:
        apenas_numeros = apenas_numeros.replace(',', '.')
    
    try:
        return float(apenas_numeros)
    except (ValueError, TypeError):
        return 0.0

@celery_app.task(bind=True, max_retries=3)
def tarefa_raspar_site(self, tarefa_id: int):
    db = SessionLocal()
    try:
        tarefa = db.query(models.TarefaAutomacao).filter(models.TarefaAutomacao.id == tarefa_id).first()
        if not tarefa:
            return f"Erro: Tarefa {tarefa_id} não encontrada."

        tarefa.status = f"rodando (tentativa {self.request.retries + 1})"
        db.commit()

        # PEGANDO O ORÇAMENTO PRIMEIRO
        custo_real = float(tarefa.preco_custo or 0)
        orcamento = float(tarefa.orcamento_maximo or 0)

        # PASSANDO O ORÇAMENTO PARA O SCRAPER
        dados_da_web = raspar_primeiro_produto(url=tarefa.site, tarefa_id=tarefa_id, orcamento=orcamento)
        
        preco_venda_num = limpar_preco(dados_da_web.get("preco"))

        lucro_real = preco_venda_num - custo_real
        margem = (lucro_real / preco_venda_num * 100) if preco_venda_num > 0 else 0

        if preco_venda_num == 0:
            viabilidade = "INVIÁVEL (NENHUM NO ORÇAMENTO OU ERRO)"
        elif orcamento > 0 and preco_venda_num <= orcamento:
            viabilidade = "VIÁVEL (DENTRO DO ORÇAMENTO)"
        elif lucro_real > 0:
            viabilidade = "VIÁVEL (COM LUCRO)"
        else:
            viabilidade = "INVIÁVEL (PREJUÍZO)"

        tarefa.preco_venda = preco_venda_num
        tarefa.status_viabilidade = viabilidade
        tarefa.analise_detalhada = f"Margem: {margem:.2f}% | Produto: {dados_da_web.get('titulo')}"
        
        # GUARDAR O LINK NA BASE DE DADOS
        tarefa.link_produto = dados_da_web.get("link", "")
        
        status_text = (dados_da_web.get("status") or "").lower()
        if "erro" in status_text:
            tarefa.status = "erro na raspagem"
        else:
            tarefa.status = "concluida"

        db.commit()
        return f"Tarefa {tarefa_id} finalizada com sucesso."

    except Exception as e:
        db.rollback()
        print(f"Erro na tarefa {tarefa_id}: {str(e)}")
        raise self.retry(exc=e, countdown=15)
    finally:
        db.close()