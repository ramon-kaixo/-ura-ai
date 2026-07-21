"""Router — estado compartido: config, URLs, constantes, rate_limiter, auth."""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("core.model_router")

try:
    from router_rate_limiter import rate_limiter
except ImportError:

    class _NoOpRateLimiter:
        def check(self, *args, **kwargs) -> bool:
            return True

        def is_allowed(self, *args, **kwargs) -> bool:
            return True

        def wait_if_needed(self, *args, **kwargs) -> None:
            pass

        def get_metrics(self, *args, **kwargs):
            return {}

    rate_limiter = _NoOpRateLimiter()


try:
    from core.auth_layer import require_auth
    from core.auth_layer import validate as auth_validate
except ImportError:

    def auth_validate(*args, **kwargs) -> bool:  # type: ignore[misc]
        return True

    def require_auth(*args, **kwargs):  # type: ignore[misc]
        def decorator(f):
            return f

        return decorator


from core.config_manager import get_ollama_urls

POWER_MODE: str = "AUTO"
_URLS = get_ollama_urls()


def _resolve_ollama_url() -> str:
    env_url = os.environ.get("OLLAMA_URL")
    if env_url:
        log.info("OLLAMA_URL forzada por env: %s", env_url)
        return env_url
    try:
        req = urllib.request.Request(f"{_URLS['primary']}/api/tags")  # noqa: S310
        req.add_header("Connection", "close")
        with urllib.request.urlopen(req, timeout=5) as _:  # noqa: S310
            log.info("ASUS conectado: %s", _URLS["primary"])
            return _URLS["primary"]
    except Exception as e:
        log.warning("ASUS no accesible en startup: %s", e)
        return _URLS["fallback"]


OLLAMA_URL = _resolve_ollama_url()
ROUTER_PORT = 11435
DEFAULT_TIPO = "respuesta_rapida"
FALLBACK_MODEL = "qwen2.5:3b"
CACHE_TTL = 7200
