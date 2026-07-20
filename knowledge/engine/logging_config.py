"""Logging configuration — delegates to motor/observability/logging.

Consumers:
    from knowledge.engine.logging_config import setup_logging, set_correlation_id
"""

from __future__ import annotations

import os

from motor.observability.logging import (
    set_correlation_id,
)
from motor.observability.logging import (
    setup_logging as _setup_logging,
)

__all__ = ["set_correlation_id", "setup_logging"]


def setup_logging() -> None:
    structured = os.environ.get("URA_STRUCTURED_LOGS", "").strip().lower()
    if structured == "true":
        _setup_logging(level="INFO", json_output=True)
