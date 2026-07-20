"""Structured JSON logging — delegates to motor/observability/logging.

Consumers:
    from motor.platform.logging import configure_logging, ComponentLogger
"""

from __future__ import annotations

import logging
from typing import Any

from motor.observability.logging import setup_logging

configure_logging = setup_logging


class ComponentLogger:
    """Logger que inyecta component, operation y trace_id."""

    def __init__(self, component: str) -> None:
        self._component = component
        self._logger = logging.getLogger(f"ura.{component}")

    def _log(self, level: int, msg: str, **extra: Any) -> None:
        extra.setdefault("component", self._component)
        self._logger.log(level, msg, extra=extra)

    def info(self, msg: str, **extra: Any) -> None:
        self._log(logging.INFO, msg, **extra)

    def warn(self, msg: str, **extra: Any) -> None:
        self._log(logging.WARNING, msg, **extra)

    def error(self, msg: str, **extra: Any) -> None:
        self._log(logging.ERROR, msg, **extra)

    def debug(self, msg: str, **extra: Any) -> None:
        self._log(logging.DEBUG, msg, **extra)
