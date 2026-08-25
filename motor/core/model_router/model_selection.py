"""Puente temporal core -> motor: seleccion de modelos.

Re-exporta la API consumida por los clientes migrados. Implementacion
viva en core/model_router/model_selection.py (TASK-20260825-005).
"""

from __future__ import annotations

from core.model_router.model_selection import _record_success as _record_success  # noqa: PLC0414

__all__ = ["_record_success"]
