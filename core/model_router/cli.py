"""CLI — entrypoint: main() + verificar_politicas_seguridad_preflight."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from motor.core.secrets import get_secret
from motor.observability.logging import setup_logging

log = logging.getLogger(__name__)

BYPASS_FILE = Path("/home/ramon/.openclaw/bypass_config.json")


def verificar_politicas_seguridad_preflight() -> None:
    if BYPASS_FILE.exists():
        BYPASS_FILE.unlink(missing_ok=True)
    os.environ["URA_AUTH_ENABLED"] = "true"
    token_valido = get_secret("OPENCLAW_GATEWAY_TOKEN")
    if not token_valido:
        sys.exit(78)


def _ejecutar_modo_test(clasificar_peticion, obtener_modelos_disponibles, seleccionar_modelo) -> None:
    idx = sys.argv.index("--test")
    texto = " ".join(sys.argv[idx + 1 :]) if idx + 1 < len(sys.argv) else "hola"
    messages = [{"role": "user", "content": texto}]
    tipo = clasificar_peticion(messages)
    disponibles = obtener_modelos_disponibles()
    seleccionar_modelo(tipo, disponibles)


def _log_inicio(disponibles: list[str], get_ollama_url, ROUTER_PORT: int) -> None:
    log.info("Model Router Enhanced v2.2 iniciando en puerto %s", ROUTER_PORT)
    log.info("Ollama backend: %s", get_ollama_url())
    log.info("POWER_MODE: AUTO (deteccion por IP cliente) — manual TURBO/ECO via 'mode'")
    log.info("Features: Dashboard, Prompt Caching, Fallback System, Metrics, Context Checker")

    if disponibles:
        log.info("Modelos disponibles: %s", ", ".join(sorted(disponibles)))
    else:
        log.warning("Ollama no accesible en %s — se reintentara", get_ollama_url())


def _log_rutas(modelo_routes: dict, disponibles: list[str], seleccionar_modelo) -> None:
    for tipo, info in modelo_routes.items():
        modelo = seleccionar_modelo(tipo, disponibles) if disponibles else info["modelos"][0]
        fallback = info.get("fallback", "N/A")
        log.info("  %-20s → %s (fallback: %s)", tipo, modelo, fallback)


def main() -> None:
    setup_logging(level="INFO", fmt="%(asctime)s - %(levelname)s - %(message)s")

    from core.model_router.model_selection import (
        MODELO_ROUTES,
        clasificar_peticion,
        obtener_modelos_disponibles,
        seleccionar_modelo,
    )
    from core.model_router.router import ROUTER_PORT, get_ollama_url

    if "--test" in sys.argv or "--models" in sys.argv:
        pass
    else:
        verificar_politicas_seguridad_preflight()

    if "--test" in sys.argv:
        _ejecutar_modo_test(clasificar_peticion, obtener_modelos_disponibles, seleccionar_modelo)
        return
    if "--models" in sys.argv:
        obtener_modelos_disponibles()
        return

    disponibles = obtener_modelos_disponibles()
    _log_inicio(disponibles, get_ollama_url, ROUTER_PORT)
    _log_rutas(MODELO_ROUTES, disponibles, seleccionar_modelo)

    from http.server import ThreadingHTTPServer

    from core.model_router.handler import RouterHandler

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
    main()
