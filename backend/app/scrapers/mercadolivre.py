import sys
import asyncio
from playwright.sync_api import sync_playwright

def raspar_primeiro_produto(url: str, tarefa_id: int) -> str:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print(f"[{tarefa_id}] Acessando Mercado Livre...")
        page.goto(url)
        
        # 1. A SUA DESCOBERTA:
        # O robô espera até a classe exata que você encontrou aparecer na tela
        page.wait_for_selector('.poly-component__title', timeout=15000)
        
        # 2. A EXTRAÇÃO CIRÚRGICA:
        # Pega o texto do primeiro elemento que tem essa classe
        nome_produto = page.locator('.poly-component__title').first.inner_text()
        
        # Pega o primeiro preço da tela
        try:
            preco_produto = page.locator('.andes-money-amount__fraction').first.inner_text()
        except:
            preco_produto = "Preço oculto"
        
        resultado = f"{nome_produto} (R$ {preco_produto})"
        print(f"[{tarefa_id}] DADO ROUBADO COM SUCESSO: {resultado}")
        
        browser.close()
        
        return resultado