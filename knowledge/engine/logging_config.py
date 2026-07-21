"""Logging configuration — DEPRECATED. Importar directamente de motor.observability.logging."""

from __future__ import annotations

import warnings

from motor.observability.logging import (
    set_correlation_id,
)
from motor.observability.logging import (
    setup_logging as _setup_logging,
)

__all__ = ["set_correlation_id", "setup_logging"]


def setup_logging() -> None:
    warnings.warn(
        "knowledge.engine.logging_config.setup_logging is deprecated. "
        "Use motor.observability.logging.setup_logging directamente.",
        DeprecationWarning,
        stacklevel=2,
    )
    import os

    structured = os.environ.get("URA_STRUCTURED_LOGS", "").strip().lower()
    if structured == "true":
        _setup_logging(level="INFO", json_output=True)
