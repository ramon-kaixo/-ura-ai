"""Utilidades compartidas para el módulo LLM.

Funciones de logging y estadísticas usadas por múltiples proveedores.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def percentile(data: list[float], p: float) -> float:
    """Calcula el percentil p de una lista de datos."""
    if not data:
        return 0.0
    idx = max(0, min(len(data) - 1, int(len(data) * p / 100)))
    return sorted(data)[idx]


def log_call(provider: str, model: str, latency_ms: float, error: str | None = None, **extra: Any) -> None:
    """Registra una llamada LLM con métricas estructuradas.

    Formato: llm_call  provider=<name> model=<model> latency_ms=<ms> error=<err> <extra>
    """
    extra_str = " ".join(f"{k}={v}" for k, v in extra.items())
    msg = "llm_call  provider=%s model=%s latency_ms=%.0f error=%s %s"
    if error:
        log.warning(msg, provider, model, latency_ms, error, extra_str)
    else:
        log.info(msg, provider, model, latency_ms, "null", extra_str)
