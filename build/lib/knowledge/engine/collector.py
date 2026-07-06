"""Collector — file system watcher + job queue.

Envía solicitudes de compile al orquestador cuando detecta cambios.
NO ejecuta compilaciones directamente — solo encola.
"""

from knowledge.engine.orchestrator import request_compile


def collect(reason: str = "collector") -> int:
    """Detecta cambios y encola un compile.

    Retorna 1 si se encoló un trabajo, 0 si no.
    Por ahora solo es un puente hacia orchestrator.request_compile.
    En el futuro integrará inotify (debounce 2s) y git post-commit hook.
    """
    return request_compile(reason, payload={"source": "collector"})
