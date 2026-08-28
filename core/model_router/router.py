"""Router — estado compartido: config, URLs, constantes, rate_limiter, auth."""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("core.model_router")

try:
    from router_rate_limiter import rate_limiter
except ImportError:

    class _NoOpRateLimiter:
        def check(self, *args: Any, **kwargs: Any) -> bool:
            return True

        def is_allowed(self, *args: Any, **kwargs: Any) -> bool:
            return True

        def wait_if_needed(self, *args: Any, **kwargs: Any) -> None:
            pass

        def get_metrics(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {}

    rate_limiter = _NoOpRateLimiter()

# Timeouts de red por defecto (segundos)
CONN_TIMEOUT = 10
READ_TIMEOUT = 30


try:
    from core.auth_layer import require_auth
    from core.auth_layer import validate as auth_validate
except ImportError:

    def auth_validate(api_key: str | None, store: Any = None) -> bool:  # type: ignore[misc]
        return True

    def require_auth() -> bool:  # type: ignore[misc]
        return True


from motor.core.config_manager import get_ollama_urls

POWER_MODE: str = "AUTO"
_URLS: dict[str, str] | None = None


def get_urls() -> dict[str, str]:
    global _URLS  # noqa: PLW0603
    if _URLS is None:
        _URLS = get_ollama_urls()
    return _URLS


def _resolve_ollama_url() -> str:
    urls = get_urls()
    env_url = os.environ.get("OLLAMA_URL")
    if env_url:
        log.info("OLLAMA_URL forzada por env: %s", env_url)
        return env_url
    try:
        req = urllib.request.Request(f"{urls['primary']}/api/tags")  # noqa: S310
        req.add_header("Connection", "close")
        with urllib.request.urlopen(req, timeout=CONN_TIMEOUT) as _:  # noqa: S310
            log.info("ASUS conectado: %s", urls["primary"])
            primary: str = urls["primary"]
            return primary
    except Exception as e:
        log.warning("ASUS no accesible en startup: %s", e)
        fallback: str = urls["fallback"]
        return fallback


_OLLAMA_URL: str | None = None


def get_ollama_url() -> str:
    global _OLLAMA_URL  # noqa: PLW0603
    if _OLLAMA_URL is None:
        _OLLAMA_URL = _resolve_ollama_url()
    return _OLLAMA_URL


ROUTER_PORT = 11435


DEFAULT_TIPO = "respuesta_rapida"
FALLBACK_MODEL = "llama3:latest"
CACHE_TTL = 7200
