"""Collector — file system watcher + job queue.

Envía solicitudes de compile al orquestador cuando detecta cambios.
NO ejecuta compilaciones directamente — solo encola.

CUIDADO: No produce side effects al importar. La inicialización del
EventBus ocurre en la primera llamada a collect(), no en el import.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.engine.orchestrator import request_compile

_BUS_INITIALIZED = False


def _ensure_bus() -> None:
    """Inicializa el EventBus una sola vez (lazy, en primera llamada)."""
    global _BUS_INITIALIZED  # noqa: PLW0603
    if _BUS_INITIALIZED:
        return
    from knowledge.engine.eventbus import get_bus
    from knowledge.engine.subscribers import subscribe_all

    bus = get_bus()
    subscribe_all(bus, Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db", Path())
    _BUS_INITIALIZED = True


def collect(reason: str = "collector") -> int:
    """Detecta cambios y encola un compile.

    Retorna 1 si se encoló un trabajo, 0 si no.
    Por ahora solo es un puente hacia orchestrator.request_compile.
    En el futuro integrará inotify (debounce 2s) y git post-commit hook.
    """
    _ensure_bus()
    return request_compile(reason, payload={"source": "collector"})
