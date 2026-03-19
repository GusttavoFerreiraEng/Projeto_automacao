import os
import json
import logging
import time
from google import genai 
from .prompts import PROMPT_FILTRO_COMPRAS
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("DinoAI")

def analisar_ofertas_com_ia(html_texto, orcamento, produto_desejado):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    prompt_final = PROMPT_FILTRO_COMPRAS.format(
        produto_desejado=produto_desejado, 
        orcamento=f"{orcamento:.2f}"
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=[prompt_final, html_texto[:2000]] 
        )
        
        if not response.text:
            raise ValueError("Resposta vazia da IA")

        texto_limpo = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(texto_limpo)
        
    except Exception as e:
        logger.error(f"Erro na chamada do Gemini: {e}")
        return {
            "encontrou": False, 
            "modelo": "Dino em Manutenção", 
            "motivo": "O Google pediu um tempo (Erro de Cota). Tente novamente em instantes.",
            "preco": 0.0,
            "link": ""
        }