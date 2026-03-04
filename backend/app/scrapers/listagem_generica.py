import sys
import asyncio
from playwright.sync_api import sync_playwright

def raspar_titulo(url: str, tarefa_id: int) -> str:
    """
    Função isolada que apenas entra no site e devolve o título.
    Não sabe nada sobre Banco de Dados ou Celery.
    """
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        
        titulo = page.title()
        print(f"[{tarefa_id}] SUCESSO NO SCRAPER! O título é: {titulo}")
        
        browser.close()
        

        return titulo