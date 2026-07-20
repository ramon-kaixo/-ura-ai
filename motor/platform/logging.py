"""Structured JSON logging configuration for URA platform.

Usage:
    from motor.platform.logging import configure_logging
    configure_logging(level="INFO")
    logger.info("message", extra={"key": "value"})

    # ComponentLogger auto-injects component, operation, trace_id
    log = ComponentLogger("f25_fusion")
    log.info("Operation completed", operation="fuse", duration_ms=45)
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Formato JSON para logs. Cada línea es un JSON válido."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        _add_standard_fields(record, log_entry)
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def _add_standard_fields(record: logging.LogRecord, entry: dict[str, Any]) -> None:
    for field in ("component", "operation", "trace_id", "span_id", "duration_ms"):
        val = getattr(record, field, None)
        if val is not None:
            entry[field] = val


class PlainFormatter(logging.Formatter):
    """Formato texto plano para desarrollo."""

    def format(self, record: logging.LogRecord) -> str:
        return f"[{record.levelname[0]}] {record.name}: {record.getMessage()}"


def configure_logging(
    level: str = "INFO",
    structured: bool = False,
    output: str | None = None,
) -> None:
    """Configura logging global.

    Args:
        level: DEBUG, INFO, WARN, ERROR
        structured: True=JSON, False=texto plano
        output: ruta de archivo o None=stdout

    """
    handler: logging.Handler
    handler = logging.FileHandler(output) if output else logging.StreamHandler(sys.stdout)

    handler.setFormatter(StructuredFormatter() if structured else PlainFormatter())

    root = logging.getLogger("ura")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)


class ComponentLogger:
    """Logger que inyecta component, operation y trace_id automáticamente.

    Cumple OB04: cada log incluye component, operation, trace_id (si disponible).
    """

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
