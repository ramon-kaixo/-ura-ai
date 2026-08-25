"""Puente temporal core -> motor: seleccion de modelos.

Reenvia dinamicamente (PEP 562) a core.model_router.model_selection
(TASK-20260825-005).

DEPRECATED: usar core.model_router.model_selection directamente (TASK-20260825-006).
"""

from __future__ import annotations

import warnings
from typing import Any

import core.model_router.model_selection as _core


def __getattr__(name: str) -> Any:
    warnings.warn(
        f"Importing {name} from {__name__} is deprecated. Use core.model_router.model_selection directly.",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(_core, name)


__all__ = ["_record_success"]  # noqa: F822
