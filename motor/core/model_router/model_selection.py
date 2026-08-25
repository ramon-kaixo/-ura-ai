"""Puente temporal core -> motor: seleccion de modelos.

Reenvia dinamicamente (PEP 562) a core.model_router.model_selection
(TASK-20260825-005).
"""

from __future__ import annotations

from typing import Any

import core.model_router.model_selection as _core


def __getattr__(name: str) -> Any:
    return getattr(_core, name)


__all__ = ["_record_success"]  # noqa: F822
