import re
import logging
from urllib.parse import urlparse
from .exceptions import ScraperURLError

logger = logging.getLogger(__name__)

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
    except (ValueError, TypeError) as e:
        logger.warning(f"Erro ao converter preço '{valor}': {type(e).__name__}: {e}")
        return 0.0
    
def validar_url_especifica(url: str):
    parsed = urlparse(url)
    if not parsed.path or parsed.path == "/":
        raise ScraperURLError(f"URL genérica detectada: {url}. O Dino precisa de um link de produto ou busca.")