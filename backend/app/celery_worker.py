import traceback
import re
from celery import Celery
from .database import SessionLocal
from . import models
from .scrapers.mercadolivre import raspar_primeiro_produto

celery_app = Celery(
    "worker_automacao",
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0"
)

def limpar_preco(preco_str):
     if not preco_str or preco_str == "0" or preco_str == "R$ 0":
        return 0.0

     # Remove R$, pontos de milhar e espaços, mantém a vírgula/ponto decimal
     apenas_numeros = re.sub(r'[^\d,.]', '', preco_str)
     
     # Se o formato brasileiro vier com ponto no milhar (ex: 4.718), remove o ponto
     # Se vier com vírgula decimal, trocamos por ponto
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
        if not tarefa:
            return "Erro: Tarefa não encontrada."

        tarefa.status = f"rodando (tentativa {self.request.retries + 1})"
        db.commit()

        # O robô agora recebe um dicionário {'titulo': ..., 'preco': ...}
        dados_da_web = raspar_primeiro_produto(url=tarefa.site_alvo, tarefa_id=tarefa_id)

        # --- A MUDANÇA ESTÁ AQUI ---
        
        # 1. Pegamos o custo que a API salvou (Ex: "R$ 3.500,00") e limpamos para número
        custo_real = limpar_preco(tarefa.preco_custo)
        
        # 2. Limpamos o preço de venda que veio da raspagem
        preco_venda_num = limpar_preco(dados_da_web.get("preco"))
        
        # 3. Fazemos a conta com valores REAIS
        lucro_real = preco_venda_num - custo_real
        
        # Cálculo da margem (evitando divisão por zero)
        margem_percentual = (lucro_real / preco_venda_num) * 100 if preco_venda_num > 0 else 0

        # 4. Atualizamos o banco
        tarefa.preco_venda = f"R$ {preco_venda_num:,.2f}"
        # O preco_custo já foi salvo pela rota do FastAPI, então não precisamos mexer, 
        # mas se quiser garantir a formatação:
        tarefa.preco_custo = f"R$ {custo_real:,.2f}"
        
        tarefa.margem_lucro = f"{margem_percentual:.2f}% (R$ {lucro_real:,.2f})"
        tarefa.analise_produtos = dados_da_web.get("titulo")
        
        if "erro" in dados_da_web.get("status"):
            tarefa.status = "erro na raspagem"
        else:
            tarefa.status = "concluida"

        db.commit()
        return f"Sucesso: {dados_da_web.get('titulo')} | Lucro: R$ {lucro_real:.2f}"

    except Exception as e:
        tentativa_atual = self.request.retries + 1
        if tentativa_atual <= self.max_retries:
            if 'tarefa' in locals() and tarefa:
                tarefa.status = f"falhou. aguardando tentativa {tentativa_atual + 1}..."
                db.commit()
            raise self.retry(exc=e, countdown=10)
        else:
            if 'tarefa' in locals() and tarefa:
                tarefa.status = "erro fatal: site fora do ar"
                db.commit()
            return "Erro Fatal"
    
    finally:
        db.close()