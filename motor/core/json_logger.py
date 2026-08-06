"""Structured JSON logging — delegates to motor/observability/logging.

DEPRECATED: Use motor.platform.logging.ComponentLogger o
motor.observability.logging directamente en código nuevo.
"""

from __future__ import annotations

import logging
import sys
import warnings
from typing import Any

from motor.observability.logging import JSONFormatter


class StructuredLogger:
    """Wrapper alrededor de logging.Logger que emite JSON structurado.

    Deprecated: Usar motor.platform.logging.ComponentLogger.
    """

    def __init__(self, name: str, level: int = logging.INFO) -> None:
        warnings.warn(
            "StructuredLogger is deprecated. Use motor.platform.logging.ComponentLogger.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.handlers.clear()

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        self._logger.addHandler(handler)

    def info(self, msg: str, **extra: Any) -> None:
        self._logger.info(msg, extra={"extra": extra} if extra else None)

    def warning(self, msg: str, **extra: Any) -> None:
        self._logger.warning(msg, extra={"extra": extra} if extra else None)

    def error(self, msg: str, **extra: Any) -> None:
        self._logger.error(msg, extra={"extra": extra} if extra else None)

    def critical(self, msg: str, **extra: Any) -> None:
        self._logger.critical(msg, extra={"extra": extra} if extra else None)

    def debug(self, msg: str, **extra: Any) -> None:
        self._logger.debug(msg, extra={"extra": extra} if extra else None)
