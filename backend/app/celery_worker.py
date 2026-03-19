import os
import re
import logging
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
from .database import SessionLocal
from urllib.parse import urlparse
from . import models
from .scrapers.mercadolivre import raspar_primeiro_produto
from .scrapers.amazon import raspar_amazon
from .scrapers.shopee import raspar_shopee
from .exceptions import ScraperBlockedError, ScraperLayoutError, ScraperTimeoutError, ScraperURLError
from .ai.agent import analisar_ofertas_com_ia 

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("DinoLogger")

SCRAPERS_MAP = {
    "amazon.com": raspar_amazon,
    "shopee.com": raspar_shopee,
    "mercadolivre.com": raspar_primeiro_produto,
    "mlstatic.com": raspar_primeiro_produto
}

# Configuração Celery
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("worker_automacao", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.beat_schedule = {
    'verificar_precos_todos_os_dias_de_manha': {
        'task': 'app.celery_worker.verificar_precos_diariamente',
        'schedule': crontab(hour=8, minute=0)
    }
}
celery_app.conf.timezone = 'America/Sao_Paulo' 

def obter_scraper_adequado(url: str):
    url_lower = url.lower()
    for dominio, funcao in SCRAPERS_MAP.items():
        if dominio in url_lower:
            return funcao
    return raspar_primeiro_produto

def validar_url_especifica(url: str):
    parsed = urlparse(url)
    if not parsed.path or parsed.path == "/":
        raise ScraperURLError(f"URL genérica detectada: {url}. O Dino precisa de um link de produto ou busca.")

def limpar_preco(valor):
    if valor is None: return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    apenas_numeros = re.sub(r'[^\d,.]', '', str(valor))
    if ',' in apenas_numeros and '.' in apenas_numeros:
        apenas_numeros = apenas_numeros.replace('.', '').replace(',', '.')
    elif ',' in apenas_numeros:
        apenas_numeros = apenas_numeros.replace(',', '.')
    try:
        return float(apenas_numeros)
    except:
        return 0.0

@celery_app.task(bind=True, max_retries=3)
def tarefa_raspar_site(self, tarefa_id: int):
    db = SessionLocal()
    try:
        tarefa = db.query(models.TarefaAutomacao).filter(models.TarefaAutomacao.id == tarefa_id).first()
        if not tarefa: return f"Erro: Tarefa {tarefa_id} não encontrada."

        tarefa.status = f"rodando (tentativa {self.request.retries + 1})"
        db.commit()

        funcao_scraper = obter_scraper_adequado(tarefa.site)
        logger.info(f"Tarefa {tarefa_id}: Usando scraper {funcao_scraper.__name__} para {tarefa.site}")

        try:
            validar_url_especifica(tarefa.site)

            custo_real = float(tarefa.preco_custo or 0)
            orcamento = float(tarefa.orcamento_maximo or 0)

            # Execução do scraper original
            dados_da_web = funcao_scraper(url=tarefa.site, tarefa_id=tarefa_id, orcamento=orcamento)
            
            #INJEÇÃO DA IA
            try:
                texto_para_analise = dados_da_web.get("conteudo_texto") or dados_da_web.get("titulo")
                
                if texto_para_analise:
                    logger.info(f"Tarefa {tarefa_id}: Solicitando análise do Gemini para melhor oferta...")
                    resultado_ai = analisar_ofertas_com_ia(
                        html_texto=texto_para_analise,
                        orcamento=orcamento,
                        produto_desejado=tarefa.site
                    )
                    
                    #Ver o que a IA cuspiu no terminal
                    logger.info(f"DINO IA RESPONDEU: {resultado_ai}")
                    
                    if resultado_ai.get("encontrou"):
                        # Sobrescreve os dados da web com a escolha inteligente da IA
                        dados_da_web["preco"] = resultado_ai.get("preco")
                        dados_da_web["titulo"] = resultado_ai.get("modelo")
                        dados_da_web["link"] = resultado_ai.get("link")
                        # Preenche a análise detalhada imediatamente
                        tarefa.analise_detalhada = f"IA escolheu: {resultado_ai.get('modelo')}. Motivo: {resultado_ai.get('motivo')}"
                    else:
                        logger.warning(f"Tarefa {tarefa_id}: IA não encontrou ofertas válidas.")
            except Exception as ai_err:
                logger.error(f"Erro na IA da tarefa {tarefa_id} (seguindo com dados brutos): {ai_err}")
            # FIM DA INJEÇÃO DA IA 

            preco_venda_num = limpar_preco(dados_da_web.get("preco"))
            
            if preco_venda_num == 0:
                tarefa.status = "erro na raspagem"
                tarefa.status_viabilidade = "INVIÁVEL (NENHUM NO ORÇAMENTO OU ERRO)"
                tarefa.analise_detalhada = "O scraper nao encontrou informacoes de preco na pagina."
                db.commit()
                return f"Tarefa {tarefa_id} finalizada sem preco encontrado."
            
            novo_historico = models.HistoricoPreco(
                tarefa_id=tarefa.id,
                preco_venda=preco_venda_num
            )
            db.add(novo_historico)

            lucro_real = preco_venda_num - custo_real
            margem = (lucro_real / preco_venda_num * 100) if preco_venda_num > 0 else 0

            if orcamento > 0 and preco_venda_num <= orcamento:
                viabilidade = "VIÁVEL (DENTRO DO ORÇAMENTO)"
            elif lucro_real > 0:
                viabilidade = "VIÁVEL (COM LUCRO)"
            else:
                viabilidade = "INVIÁVEL (PREJUÍZO)"

            # SALVANDO OS DADOS FINAIS
            tarefa.preco_venda = preco_venda_num
            tarefa.status_viabilidade = viabilidade
            tarefa.link_produto = dados_da_web.get("link", "")
            
            # Se a IA não preencheu, coloca o padrão de margem
            if not tarefa.analise_detalhada:
                tarefa.analise_detalhada = f"Margem: {margem:.2f}% | Produto: {dados_da_web.get('titulo')}"
            
            status_text = (dados_da_web.get("status") or "").lower()
            tarefa.status = "erro na raspagem" if "erro" in status_text or "bloqueio" in status_text else "concluida"

        except ScraperURLError as e:
            logger.error(f"URL INVÁLIDA: {tarefa_id}: {e}")
            tarefa.status = "URL inválida"
            tarefa.analise_detalhada = str(e)
            db.commit()
            return f"Tarefa {tarefa_id} interrompida por URL inválida."

        except ScraperBlockedError as e:
            logger.warning(f"BLOQUEIO: {tarefa_id} foi barrado: {e}")
            tarefa.status = "bloqueado (captcha/login)"
            tarefa.analise_detalhada = f"Bloqueio detectado: {str(e)}"
            db.commit()
            return f"Tarefa {tarefa_id} interrompida por bloqueio."

        except ScraperLayoutError as e:
            logger.error(f"LAYOUT: {tarefa_id} mudou: {e}")
            tarefa.status = "erro de layout"
            tarefa.analise_detalhada = f"Erro de estrutura no site: {str(e)}"
            db.commit()
            return f"Tarefa {tarefa_id} interrompida por erro de layout."

        except ScraperTimeoutError as e:
            logger.warning(f"TIMEOUT: {tarefa_id} demorou demais: {e}")
            tarefa.status = "timeout"
            tarefa.analise_detalhada = "O site demorou muito para carregar os elementos."
            db.commit()
            return f"Tarefa {tarefa_id} interrompida por timeout."

        except Exception as e:
            logger.critical(f"ERRO CRÍTICO DESCONHECIDO: {tarefa_id}: {str(e)}")
            raise self.retry(exc=e, countdown=60)

        db.commit()
        logger.info(f"Tarefa {tarefa_id} finalizada com sucesso.")
        return f"Tarefa {tarefa_id} concluída."

    except Exception as e:
        db.rollback()
        logger.error(f"Erro na tarefa {tarefa_id}: {str(e)}")
        raise self.retry(exc=e, countdown=15)
    finally:
        db.close()

@celery_app.task
def verificar_precos_diariamente():
    db = SessionLocal()
    try:
        tarefas = db.query(models.TarefaAutomacao).filter(
            models.TarefaAutomacao.status != "URL inválida"
        ).all()
        for t in tarefas:
            tarefa_raspar_site.delay(t.id)
        return f"Dino agendou {len(tarefas)} tarefas."
    finally:
        db.close()