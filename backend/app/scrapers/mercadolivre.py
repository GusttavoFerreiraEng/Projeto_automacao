import sys
import asyncio
from playwright.sync_api import sync_playwright

def raspar_primeiro_produto(url: str, tarefa_id: int) -> dict:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            # viewport={'width': 1920, 'height': 1080}
            no_viewport=True
        )
        page = context.new_page()
        context.clear_cookies()
        
        try:
            print(f"[{tarefa_id}] Acessando URL com disfarce...")
            # Aumentamos o timeout e esperamos a rede acalmar
            page.goto(url, timeout=60000, wait_until="networkidle")
            
            # 1. Aguarda o título (âncora da página)
            page.wait_for_selector('.poly-component__title', timeout=15000)
            nome_produto = page.locator('.poly-component__title').first.inner_text()
            
            #extração de preço
            preco_produto = "0"
            
            # Lista de seletores de preço comuns no Mercado Livre (Lista e Anúncio)
            seletores_preco = [
                '.andes-money-amount__fraction',
                '.poly-price__current .andes-money-amount__fraction',
                '.ui-pdp-price__part .andes-money-amount__fraction',
                '[itemprop="price"]'
            ]
            
            for seletor in seletores_preco:
                try:
                    elemento = page.locator(seletor).first
                    if elemento.is_visible(timeout=2000):
                        texto = elemento.inner_text()
                        if texto and texto.strip():
                            preco_produto = texto.strip()
                            print(f"[{tarefa_id}] Preço capturado com: {seletor}")
                            break
                except:
                    continue

            browser.close()
            return {
                "titulo": nome_produto,
                "preco": f"R$ {preco_produto}",
                "status": "sucesso"
            }

        except Exception as e:
            if 'browser' in locals():
                browser.close()
            return {
                "titulo": "Erro na captura",
                "preco": "0",
                "status": f"erro: {str(e)}"
            }