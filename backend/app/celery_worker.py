import os
import logging
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
from .database import SessionLocal
from . import models
from .scrapers.mercadolivre import raspar_mercadolivre
from .exceptions import ScraperBlockedError, ScraperLayoutError, ScraperTimeoutError, ScraperURLError
from urllib.parse import urlparse

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("worker_automacao", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.timezone = "America/Sao_Paulo"
celery_app.conf.beat_schedule = {
    "verificar_precos_diariamente": {
        "task": "app.celery_worker.verificar_precos_diariamente",
        "schedule": crontab(hour=8, minute=0),
    }
}


def _validar_url(url: str):
    """Rejeita URLs genéricas (só o domínio, sem caminho de produto ou busca)."""
    parsed = urlparse(url)
    if not parsed.path or parsed.path == "/":
        raise ScraperURLError(
            f"URL genérica demais: {url}. Envie um link de produto ou de busca."
        )


def _calcular_viabilidade(preco_venda: float, preco_custo: float, orcamento: float) -> str:
    if orcamento > 0 and preco_venda <= orcamento:
        return "VIÁVEL (dentro do orçamento)"
    lucro = preco_venda - preco_custo
    if lucro > 0:
        return "VIÁVEL (com lucro)"
    return "INVIÁVEL (prejuízo)"


@celery_app.task(bind=True, max_retries=3)
def tarefa_raspar_site(self, tarefa_id: int):
    db = SessionLocal()
    try:
        tarefa = db.query(models.TarefaAutomacao).filter(
            models.TarefaAutomacao.id == tarefa_id
        ).first()

        if not tarefa:
            logger.error(f"Tarefa {tarefa_id} não encontrada no banco.")
            return

        # Marca como em processamento
        tarefa.status = f"processando (tentativa {self.request.retries + 1})"
        db.commit()

        try:
            _validar_url(tarefa.site)

            dados = raspar_mercadolivre(
                url=tarefa.site,
                tarefa_id=tarefa_id,
                orcamento=float(tarefa.orcamento or 0),
            )

        except ScraperURLError as e:
            logger.warning(f"[tarefa {tarefa_id}] URL inválida: {e}")
            tarefa.status = "erro_url"
            tarefa.analise = str(e)
            db.commit()
            return

        except ScraperBlockedError as e:
            logger.warning(f"[tarefa {tarefa_id}] Bloqueado: {e}")
            tarefa.status = "bloqueado"
            tarefa.analise = f"Site bloqueou o robô: {e}"
            db.commit()
            return

        except ScraperLayoutError as e:
            logger.error(f"[tarefa {tarefa_id}] Layout mudou: {e}")
            tarefa.status = "erro_layout"
            tarefa.analise = f"Estrutura do site mudou: {e}"
            db.commit()
            return

        except ScraperTimeoutError as e:
            logger.warning(f"[tarefa {tarefa_id}] Timeout: {e}")
            tarefa.status = "timeout"
            tarefa.analise = "O site demorou demais para responder."
            db.commit()
            # Timeout tem retry automático
            raise self.retry(exc=e, countdown=60)

        except Exception as e:
            logger.critical(f"[tarefa {tarefa_id}] Erro desconhecido: {e}")
            raise self.retry(exc=e, countdown=60)

        preco_venda = float(dados.get("preco") or 0)

        if preco_venda == 0:
            tarefa.status = "sem_resultado"
            tarefa.analise = "Nenhum produto encontrado no orçamento ou preço não capturado."
            db.commit()
            return

        preco_custo = float(tarefa.preco_custo or 0)
        orcamento = float(tarefa.orcamento or 0)
        margem = ((preco_venda - preco_custo) / preco_venda * 100) if preco_venda > 0 else 0

        # Salva histórico de preço
        db.add(models.HistoricoPreco(tarefa_id=tarefa.id, preco_venda=preco_venda))

        tarefa.preco_venda = preco_venda
        tarefa.link_produto = dados.get("link", "")
        tarefa.status_viabilidade = _calcular_viabilidade(preco_venda, preco_custo, orcamento)
        tarefa.analise = (
            f"Produto: {dados.get('titulo')} | "
            f"Preço: R$ {preco_venda:.2f} | "
            f"Margem: {margem:.1f}%"
        )
        tarefa.status = "concluida"
        db.commit()

        logger.info(f"[tarefa {tarefa_id}] Concluída — {tarefa.status_viabilidade}")

    except Exception as e:
        db.rollback()
        logger.error(f"[tarefa {tarefa_id}] Erro no worker: {e}")
        raise self.retry(exc=e, countdown=15)
    finally:
        db.close()


@celery_app.task
def verificar_precos_diariamente():
    """Reagenda todas as tarefas concluídas para atualizar os preços todo dia às 8h."""
    db = SessionLocal()
    try:
        tarefas = db.query(models.TarefaAutomacao).filter(
            models.TarefaAutomacao.status == "concluida"
        ).all()
        for t in tarefas:
            tarefa_raspar_site.delay(t.id)
        logger.info(f"Agendou {len(tarefas)} tarefas para verificação diária.")
        return f"Agendadas: {len(tarefas)} tarefas."
    finally:
        db.close()