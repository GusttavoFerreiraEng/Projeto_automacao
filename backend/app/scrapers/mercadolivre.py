import sys
import asyncio
from playwright.sync_api import sync_playwright
from ..exceptions import ScraperBlockedError, ScraperLayoutError, ScraperTimeoutError


def raspar_mercadolivre(url: str, tarefa_id: int, orcamento: float = 0.0) -> dict:
    """
    Raspa o Mercado Livre a partir de uma URL de produto ou de busca.
    Retorna dict com: titulo, preco (float), link, status.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True,
            bypass_csp=True,
        )
        page = context.new_page()

        try:
            print(f"[tarefa {tarefa_id}] Acessando: {url} | orçamento: R$ {orcamento}")
            page.goto(url, timeout=60000)
            page.wait_for_timeout(3000)

            # Scroll suave para carregar os cards
            for _ in range(3):
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(800)

            # Página de produto único
            if page.locator("h1.ui-pdp-title").count() > 0:
                titulo = page.locator("h1.ui-pdp-title").first.text_content().strip()
                preco_el = page.locator(
                    ".ui-pdp-price__second-line .andes-money-amount__fraction"
                ).first
                if preco_el.count() == 0:
                    raise ScraperLayoutError("Seletor de preço não encontrado na página de produto.")
                preco_str = preco_el.text_content().replace(".", "").strip()
                preco = float(preco_str)
                browser.close()
                return {
                    "titulo": titulo,
                    "preco": preco,
                    "link": url,
                    "status": "concluida",
                }

            # Página de busca (lista de cards)
            cards = page.locator(".ui-search-layout__item, .poly-card").all()
            print(f"[tarefa {tarefa_id}] {len(cards)} cards encontrados")

            if len(cards) == 0:
                # Captura screenshot para diagnóstico
                page.screenshot(path=f"debug_ml_{tarefa_id}.png", full_page=True)
                raise ScraperLayoutError("Nenhum card encontrado. Seletores podem ter mudado.")

            for card in cards:
                try:
                    titulo_el = card.locator(
                        "h2, .ui-search-item__title, .poly-component__title"
                    ).first
                    preco_el = card.locator(".andes-money-amount__fraction").first
                    link_el = card.locator("a").first

                    if titulo_el.count() == 0 or preco_el.count() == 0:
                        continue

                    titulo_txt = titulo_el.text_content().strip()
                    preco_str = preco_el.text_content().replace(".", "").strip()
                    preco_num = float(preco_str)
                    link = link_el.get_attribute("href") if link_el.count() > 0 else ""

                    # Ignora preços suspeitos (centavos = provavelmente acessório)
                    if preco_num < 10:
                        continue

                    # Com orçamento: retorna o primeiro que cabe
                    if orcamento > 0:
                        if preco_num <= orcamento:
                            print(f"[tarefa {tarefa_id}] Achou dentro do orçamento: {titulo_txt} — R$ {preco_num}")
                            browser.close()
                            return {
                                "titulo": titulo_txt,
                                "preco": preco_num,
                                "link": link,
                                "status": "concluida",
                            }
                    else:
                        # Sem orçamento: retorna o primeiro produto válido
                        print(f"[tarefa {tarefa_id}] Primeiro produto: {titulo_txt} — R$ {preco_num}")
                        browser.close()
                        return {
                            "titulo": titulo_txt,
                            "preco": preco_num,
                            "link": link,
                            "status": "concluida",
                        }
                except Exception:
                    continue

            # Nenhum produto encontrado dentro do orçamento
            browser.close()
            return {
                "titulo": "Nenhum produto encontrado no orçamento informado",
                "preco": 0.0,
                "link": "",
                "status": "sem_resultado",
            }

        except ScraperLayoutError:
            browser.close()
            raise
        except Exception as e:
            browser.close()
            raise ScraperTimeoutError(str(e)) from e