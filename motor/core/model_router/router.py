"""Puente temporal core -> motor: router del Model Router.

Re-exporta la API consumida por los clientes migrados. Implementacion
viva en core/model_router/router.py (TASK-20260825-005).
"""

from __future__ import annotations

from core.model_router.router import CONN_TIMEOUT as CONN_TIMEOUT  # noqa: PLC0414
from core.model_router.router import READ_TIMEOUT as READ_TIMEOUT  # noqa: PLC0414
from core.model_router.router import get_urls as get_urls  # noqa: PLC0414

__all__ = ["CONN_TIMEOUT", "READ_TIMEOUT", "get_urls"]
