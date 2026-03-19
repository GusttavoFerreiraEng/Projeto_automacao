import sys
import asyncio
import os
from playwright.sync_api import sync_playwright

def raspar_shopee(url: str, tarefa_id: int, orcamento: float = 0.0) -> dict:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


    user_data_dir = os.path.join(os.getcwd(), "shopee_session")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-infobars',
                '--start-maximized',
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768}
        )
        
        page = context.pages[0]
        
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            print(f"[{tarefa_id}] Dino tentando drible na Shopee: {url}")
            
           
            page.goto("https://shopee.com.br", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)
            
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            
            page.wait_for_timeout(5000)
            page.keyboard.press("Escape")
            
            for i in range(4):
                page.mouse.wheel(0, 800)
                page.wait_for_timeout(1500)

            cards = page.locator('a[data-sqe="link"], a[href*="-i."]').all()
            
            print(f"[{tarefa_id}] Dino avistou {len(cards)} possíveis itens.")

            if len(cards) == 0:
                page.screenshot(path=f"erro_shopee_{tarefa_id}.png")
                if "login" in page.url:
                    return {"titulo": "Caiu no Login", "preco": "0", "link": url, "status": "bloqueio"}
                return {"titulo": "Bloqueado ou Vazio", "preco": "0", "link": url, "status": "bloqueio"}

            for card in cards:
                try:
                    info_card = card.inner_text()
                    
                    if "R$" in info_card:
                        linhas = info_card.split("\n")
                        titulo_txt = linhas[0].strip()
                        
                        import re
                        precos_achados = re.findall(r'R\$\s?([\d\.,]+)', info_card)
                        
                        if precos_achados:
                            preco_limpo = precos_achados[0].replace('.', '').replace(',', '.')
                            preco_num = float(preco_limpo)
                            
                            link = card.get_attribute('href')
                            if link and not link.startswith('http'):
                                link = "https://shopee.com.br" + link

                            if orcamento == 0 or preco_num <= orcamento:
                                print(f"[{tarefa_id}] 🦖: {titulo_txt[:30]} por R$ {preco_num}")
                                return {"titulo": titulo_txt, "preco": str(preco_num), "link": link, "status": "sucesso"}
                except Exception as e:
                    continue

            return {"titulo": "Nada no orçamento", "preco": "0", "link": "", "status": "sucesso"}

        finally:
            context.close()