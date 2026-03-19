import sys
import asyncio
from playwright.sync_api import sync_playwright

def raspar_primeiro_produto(url: str, tarefa_id: int, orcamento: float = 0.0) -> dict:
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        ) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            java_script_enabled=True,
            bypass_csp=True 
        )
        page = context.new_page()
        
        try:
            print(f"[{tarefa_id}] Buscando ofertas em: {url} | Orçamento Máximo: R$ {orcamento}")
            page.goto(url, timeout=60000)
            page.wait_for_timeout(4000) 
            
            print(f"[{tarefa_id}] Rolando a página para carregar os produtos...")
            for i in range(3):
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(1000)

            # CAPTURA DE TEXTO PARA IA: Pegamos o texto visível da página inteira
            # Isso alimenta o 'conteudo_texto' que o seu worker espera
            texto_para_ia = page.locator('body').inner_text()

            # É A PÁGINA DE UM PRODUTO ÚNICO
            titulo_unico = page.locator('h1.ui-pdp-title')
            if titulo_unico.count() > 0:
                titulo = titulo_unico.first.text_content()
                preco_el = page.locator('.ui-pdp-price__second-line .andes-money-amount__fraction').first
                preco = preco_el.text_content().replace('.', '') if preco_el.count() > 0 else "0"
                
                return {
                    "titulo": titulo.strip(), 
                    "preco": preco, 
                    "link": url, 
                    "status": "sucesso",
                    "conteudo_texto": texto_para_ia # Adicionado para IA
                }

            # É UMA PÁGINA DE BUSCA (VÁRIOS PRODUTOS)
            print(f"[{tarefa_id}] Lendo a lista de produtos...")
            produtos_na_busca = page.locator('.ui-search-layout__item, .poly-card').all()
            
            print(f"[{tarefa_id}] Encontrei {len(produtos_na_busca)} cards na tela.")

            if len(produtos_na_busca) == 0:
                nome_arquivo = f"erro_tela_tarefa_{tarefa_id}.png"
                print(f"[{tarefa_id}] Tirando foto da tela para investigar. Arquivo: {nome_arquivo}")
                page.screenshot(path=nome_arquivo, full_page=True)

            for produto in produtos_na_busca:
                try:
                    titulo_el = produto.locator('h2, .ui-search-item__title, .poly-component__title').first
                    preco_el = produto.locator('.andes-money-amount__fraction').first
                    link_el = produto.locator('a').first
                    link_texto = link_el.get_attribute('href') if link_el.count() > 0 else ""
                    
                    if titulo_el.count() > 0 and preco_el.count() > 0:
                        titulo_texto = titulo_el.text_content()
                        preco_texto = preco_el.text_content()
                        
                        if titulo_texto and preco_texto:
                            titulo_texto = titulo_texto.strip()
                            preco_texto_limpo = preco_texto.replace('.', '').strip()
                            preco_num = float(preco_texto_limpo)
                            
                            if preco_num < 100:
                                continue

                            if orcamento > 0:
                                if preco_num <= orcamento:
                                    print(f"[{tarefa_id}] ACHOU! {titulo_texto} por R$ {preco_num}")
                                    browser.close()
                                    return {
                                        "titulo": titulo_texto, 
                                        "preco": preco_texto_limpo, 
                                        "link": link_texto, 
                                        "status": "sucesso",
                                        "conteudo_texto": texto_para_ia # Adicionado para IA
                                    }
                            else:
                                print(f"[{tarefa_id}] Peguei o primeiro: {titulo_texto}")
                                browser.close()
                                return {
                                    "titulo": titulo_texto, 
                                    "preco": preco_texto_limpo, 
                                    "link": link_texto, 
                                    "status": "sucesso",
                                    "conteudo_texto": texto_para_ia # Adicionado para IA
                                }
                except Exception:
                    continue 
                    
            browser.close()
            return {
                "titulo": "Nenhum produto atende ao orçamento",
                "preco": "0",
                "link": "",
                "status": "sucesso",
                "conteudo_texto": texto_para_ia # Adicionado para IA
            }

        except Exception as e:
            if 'browser' in locals():
                browser.close()
            return {
                "titulo": "Erro na captura",
                "preco": "0",
                "link": "",
                "status": f"erro: {str(e)}",
                "conteudo_texto": "" # Fallback vazio em caso de erro crítico
            }