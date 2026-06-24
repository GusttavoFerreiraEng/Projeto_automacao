class DinoError(Exception):
    """Base para erros do projeto."""
    pass


class ScraperBlockedError(DinoError):
    """Site detectou o robô (captcha, login, 403)."""
    pass


class ScraperLayoutError(DinoError):
    """Site carregou, mas o seletor de preço/título mudou."""
    pass


class ScraperTimeoutError(DinoError):
    """Site não carregou no tempo limite."""
    pass


class ScraperURLError(DinoError):
    """URL genérica demais (ex: apenas a home do site)."""
    pass