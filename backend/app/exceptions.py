class DinoError(Exception):
    """Base para erros do Dino"""
    pass

class ScraperBlockedError(DinoError):
    """Quando o site detecta o robô (Captcha, Login, 403)"""
    pass

class ScraperLayoutError(DinoError):
    """O site abriu, mas não achamos o preço/título (mudaram o HTML)"""
    pass

class ScraperTimeoutError(DinoError):
    """O site não carregou a tempo"""
    pass

class ScraperURLError(DinoError):
    """Lançada quando a URL é genérica demais (ex: apenas a home)"""
    pass