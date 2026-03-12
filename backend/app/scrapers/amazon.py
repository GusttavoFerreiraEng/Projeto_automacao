import sys
import asyncio
from playwright.sync_api import sync_playwright

def raspar_amazon(url: str, tarefa_id: int, orcamento: float = 0.0) -> dict:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        
        try:
            print(f"[{tarefa_id}] Dino acessando Amazon: {url}")
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            # Espera os preços carregarem na tela
            page.wait_for_timeout(3000)

            # VERIFICA SE É PRODUTO ÚNICO
            if page.locator('#productTitle').count() > 0:
                titulo = page.locator('#productTitle').first.text_content().strip()
                # Tenta pegar o preço de várias formas (promoção, boleto, etc)
                preco_el = page.locator('.a-price .a-offscreen, #priceblock_ourprice, .a-color-price').first
                preco = preco_el.text_content().replace('R$', '').strip() if preco_el.count() > 0 else "0"
                return {"titulo": titulo, "preco": preco, "link": url, "status": "sucesso"}

            # BUSCA POR LISTA (SESSÃO DE BUSCA)
            print(f"[{tarefa_id}] Analisando lista de resultados...")
            
            # Busca por qualquer elemento que tenha um código ASIN
            # ou que seja um resultado de busca padrão
            cards = page.locator('div[data-component-type="s-search-result"], [data-asin]:not([data-asin=""])').all()
            
            print(f"[{tarefa_id}] Encontrei {len(cards)} itens. Filtrando pelo melhor preço...")

            for card in cards:
                try:
                    # Seletores flexíveis para Título e Preço
                    t_el = card.locator('h2 a span, .a-size-base-plus, .a-size-medium').first
                    p_el = card.locator('.a-price .a-offscreen, .a-color-price').first
                    l_el = card.locator('h2 a, a[href*="/dp/"]').first

                    if t_el.count() > 0 and p_el.count() > 0:
                        titulo_txt = t_el.text_content().strip()
                        preco_txt = p_el.text_content().replace('R$', '').replace('.', '').replace('\xa0', '').strip()
                        preco_num = float(preco_txt.replace(',', '.'))
                        
                        link = l_el.get_attribute('href')
                        if link and not link.startswith('http'):
                            link = "https://www.amazon.com.br" + link

                        #se o preço do card for menor que o orçamento, pegamos ele!
                        if orcamento > 0 and preco_num <= orcamento:
                            print(f"[{tarefa_id}] Sucesso! Achei {titulo_txt[:40]}... por R$ {preco_num}")
                            return {"titulo": titulo_txt, "preco": str(preco_num), "link": link, "status": "sucesso"}
                        
                        # Se não tiver orçamento, pegamos o primeiro que aparecer
                        elif orcamento == 0:
                            return {"titulo": titulo_txt, "preco": str(preco_num), "link": link, "status": "sucesso"}
                except:
                    continue

            # Se chegou aqui, não achou nada no orçamento
            page.screenshot(path=f"erro_amazon_{tarefa_id}.png")
            return {"titulo": "Nenhum produto no orçamento", "preco": "0", "link": "", "status": "sucesso"}

        finally:
            browser.close()