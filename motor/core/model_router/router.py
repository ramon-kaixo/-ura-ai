"""Puente temporal core -> motor: router del Model Router.

Reenvia dinamicamente (PEP 562) a core.model_router.router; parches
sobre el modulo de origen siguen visibles aqui (TASK-20260825-005).
"""

from __future__ import annotations

from typing import Any

import core.model_router.router as _core


def __getattr__(name: str) -> Any:
    return getattr(_core, name)


__all__ = ["CONN_TIMEOUT", "READ_TIMEOUT", "get_urls"]  # noqa: F822
