"""Router — estado compartido: config, URLs, constantes, rate_limiter, auth."""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request
import warnings

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
_URLS: dict | None = None


def get_urls() -> dict:
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
        with urllib.request.urlopen(req, timeout=5) as _:  # noqa: S310
            log.info("ASUS conectado: %s", urls["primary"])
            return urls["primary"]
    except Exception as e:
        log.warning("ASUS no accesible en startup: %s", e)
        return urls["fallback"]


_OLLAMA_URL: str | None = None


def get_ollama_url() -> str:
    global _OLLAMA_URL  # noqa: PLW0603
    if _OLLAMA_URL is None:
        _OLLAMA_URL = _resolve_ollama_url()
    return _OLLAMA_URL


ROUTER_PORT = 11435


def __getattr__(name):
    if name == "OLLAMA_URL":
        warnings.warn(
            "router.OLLAMA_URL is deprecated. Use router.get_ollama_url().",
            DeprecationWarning,
            stacklevel=2,
        )
        return get_ollama_url()
    if name == "_URLS":
        warnings.warn(
            "router._URLS is deprecated. Use router.get_urls().",
            DeprecationWarning,
            stacklevel=2,
        )
        return get_urls()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


DEFAULT_TIPO = "respuesta_rapida"
FALLBACK_MODEL = "qwen2.5:3b"
CACHE_TTL = 7200
