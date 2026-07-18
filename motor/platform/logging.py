"""Structured JSON logging configuration for URA platform.

Usage:
    from motor.platform.logging import configure_logging
    configure_logging(level="INFO")
    logger.info("message", extra={"key": "value"})
"""

from __future__ import annotations

import json
import logging
import sys


class StructuredFormatter(logging.Formatter):
    """Formato JSON para logs. Cada línea es un JSON válido."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


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
    if output:
        handler = logging.FileHandler(output)
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(StructuredFormatter() if structured else PlainFormatter())

    root = logging.getLogger("ura")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)
