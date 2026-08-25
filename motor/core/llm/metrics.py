"""Puente temporal core -> motor para metricas del Model Router.

Parte de la migracion incremental core -> motor (TASK-20260825-005).
Re-exporta el singleton `metrics`; la implementacion vive en
core/model_router/metrics.py hasta completar la migracion.
"""

from __future__ import annotations

from core.model_router.metrics import metrics as metrics  # noqa: PLC0414

__all__ = ["metrics"]
