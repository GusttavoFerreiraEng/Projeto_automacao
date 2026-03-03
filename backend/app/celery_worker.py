import traceback
from celery import Celery
from .database import SessionLocal
from . import models
from .scrapers.mercadolivre import raspar_primeiro_produto

celery_app = Celery(
    "worker_automacao",
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0"
)

# 1. "bind=True" dá à função acesso a si mesma (self).
# "max_retries=3" define o limite máximo de teimosia do robô.
@celery_app.task(bind=True, max_retries=3)
def tarefa_raspar_site(self, tarefa_id: int):
    db = SessionLocal()
    
    try:
        tarefa = db.query(models.TarefaAutomacao).filter(models.TarefaAutomacao.id == tarefa_id).first()
        if not tarefa:
            return "Erro: Tarefa não encontrada."

        tarefa.status = f"rodando (tentativa {self.request.retries + 1})"
        db.commit()
        print(f"[{tarefa_id}] Iniciando automação no site: {tarefa.site_alvo}")

        resultado_site = raspar_primeiro_produto(url=tarefa.site_alvo, tarefa_id=tarefa_id)

        tarefa.status = f"concluida ({resultado_site[:40]}...)"
        db.commit()
        return f"Finalizado com sucesso: {resultado_site}"

    except Exception as e:
        # --- LÓGICA DE RETENTATIVA ---
        tentativa_atual = self.request.retries + 1
        
        if tentativa_atual <= self.max_retries:
            # Se ainda tem tentativas, avisa no banco e tenta de novo em 10 segundos
            if 'tarefa' in locals() and tarefa:
                tarefa.status = f"falhou. aguardando tentativa {tentativa_atual + 1}..."
                db.commit()
            
            print(f"[{tarefa_id}] Site falhou. Tentando de novo em 10 segundos... ({tentativa_atual}/{self.max_retries})")
            
            # O 'countdown' é o tempo de espera (em segundos) antes de tentar de novo
            raise self.retry(exc=e, countdown=10)
        else:
            # Se já tentou 3 vezes e falhou em todas, joga a toalha
            if 'tarefa' in locals() and tarefa:
                tarefa.status = "erro fatal: site fora do ar"
                db.commit()
            
            print(f"[{tarefa_id}] Desistindo após {self.max_retries} tentativas.")
            traceback.print_exc()
            return "Erro Fatal"
    
    finally:
        db.close()