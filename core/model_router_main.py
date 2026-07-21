#!/usr/bin/env python3
"""Model Router Enhanced - Con prompt caching, fallback system, dashboard y POWER_MODE."""

from path_setup import setup_path

setup_path()
import logging
import os
import sys
from pathlib import Path

from motor.core.secrets import get_secret

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

    def auth_validate(*args, **kwargs) -> bool:
        return True

    def require_auth(*args, **kwargs):
        def decorator(f):
            return f

        return decorator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# ===== SEGURIDAD: Preflight de politicas (Tareas 0.3 y 0.6) =====
BYPASS_FILE = Path("/home/ramon/.openclaw/bypass_config.json")


def verificar_politicas_seguridad_preflight() -> None:
    """Fuerza el cumplimiento de las tareas 0.3 y 0.6. Detiene el servicio si hay configs inseguras."""
    if BYPASS_FILE.exists():
        BYPASS_FILE.unlink(missing_ok=True)
    os.environ["URA_AUTH_ENABLED"] = "true"
    token_valido = get_secret("OPENCLAW_GATEWAY_TOKEN")
    if not token_valido:
        sys.exit(78)


# NOTA: verificar_politicas_seguridad_preflight() se llama dentro de main()
# para no matar el proceso en imports (permite colección de pytest).
# ===== FIN PREFLIGHT =====

from core.config_manager import get_ollama_urls

POWER_MODE: str = "AUTO"
_URLS = get_ollama_urls()


from core.model_router.proxy import (  # noqa: F401
    _is_local_ip,
    _proxy_con_guardia_vram,
    _proxy_con_vram,
    _proxy_request_async,
    _resolve_mode_for_client,
    _resolve_ollama_url,
)
from core.model_router.vram_guard import ConcurrentVRAMGuard, vram_guard  # noqa: F401

OLLAMA_URL = _resolve_ollama_url()
ROUTER_PORT = 11435
from core.model_router.cache import PromptCache, prompt_cache  # noqa: F401
from core.model_router.handler import RouterHandler
from core.model_router.metrics import MetricsCollector, metrics  # noqa: F401
from core.model_router.model_selection import (  # noqa: F401
    MODELO_ROUTES,
    _apply_model_params,
    _get_model_params,
    _get_success_rate,
    _record_success,
    clasificar_peticion,
    obtener_modelos_disponibles,
    seleccionar_modelo,
)
from core.model_router.proxy import (  # noqa: F401
    _CHARS_PER_TOKEN,
    _CONTEXT_SUMMARY_THRESHOLD,
    _CONTEXT_WARN_THRESHOLD,
    _asus_latency_lock,
    _asus_latency_ms,
    _asus_latency_updated,
    _check_context_size,
    _estimate_tokens,
    _fallback_count_last_hour,
    _fallback_lock,
    _fallback_log,
    _get_active_backend_label,
    _measare_asus_latency,
    _register_fallback,
    _update_asus_latency,
    proxy_request,
)


def main() -> None:
    import sys

    if "--test" in sys.argv or "--models" in sys.argv:
        pass
    else:
        verificar_politicas_seguridad_preflight()

    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        texto = " ".join(sys.argv[idx + 1 :]) if idx + 1 < len(sys.argv) else "hola"
        messages = [{"role": "user", "content": texto}]
        tipo = clasificar_peticion(messages)
        disponibles = obtener_modelos_disponibles()
        modelo = seleccionar_modelo(tipo, disponibles)
        return
    if "--models" in sys.argv:
        disponibles = obtener_modelos_disponibles()
        return

    log.info("Model Router Enhanced v2.2 iniciando en puerto %s", ROUTER_PORT)
    log.info("Ollama backend: %s", OLLAMA_URL)
    log.info("POWER_MODE: AUTO (deteccion por IP cliente) — manual TURBO/ECO via 'mode'")
    log.info("Features: Dashboard, Prompt Caching, Fallback System, Metrics, Context Checker")

    disponibles = obtener_modelos_disponibles()
    if disponibles:
        log.info("Modelos disponibles: %s", ", ".join(sorted(disponibles)))
    else:
        log.warning("Ollama no accesible en %s — se reintentara", OLLAMA_URL)

    for tipo, info in MODELO_ROUTES.items():
        modelo = seleccionar_modelo(tipo, disponibles) if disponibles else info["modelos"][0]
        fallback = info.get("fallback", "N/A")
        log.info("  %-20s → %s (fallback: %s)", tipo, modelo, fallback)

    from http.server import ThreadingHTTPServer

    server = ThreadingHTTPServer(("127.0.0.1", ROUTER_PORT), RouterHandler)
    log.info("Escuchando en 127.0.0.1:%s", ROUTER_PORT)
    log.info("Dashboard: http://127.0.0.1:%s/dashboard", ROUTER_PORT)
    log.info("Metricas:  http://127.0.0.1:%s/metrics", ROUTER_PORT)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        log.info("Cerrando servidor...")
        server.server_close()
        log.info("Servidor detenido.")


if __name__ == "__main__":
    import sys

    main()
