"""Puente temporal core -> motor para metricas del Model Router.

Parte de la migracion incremental core -> motor (TASK-20260825-005).
Reenvia TODOS los atributos dinamicamente a core.model_router.metrics
(PEP 562), de modo que parches/monkeypatch sobre el modulo de origen
siguen siendo visibles a traves del puente.

DEPRECATED: usar core.model_router.metrics directamente (TASK-20260825-006).
"""

from __future__ import annotations

import warnings
from typing import Any

import core.model_router.metrics as _core


def __getattr__(name: str) -> Any:
    warnings.warn(
        f"Importing {name} from {__name__} is deprecated. Use core.model_router.metrics directly.",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(_core, name)


__all__ = ["metrics"]  # noqa: F822
