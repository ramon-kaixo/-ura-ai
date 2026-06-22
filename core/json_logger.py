"""json_logger.py — Logging estructurado JSON para todos los servicios URA.

Uso:
    from core.json_logger import StructuredLogger
    log = StructuredLogger("ura.service_name")
    log.info("mensaje", extra={"key": "value"})
    log.error("fallo", extra={"error": str(e), "latency_ms": 150})
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Formatea logs como JSON de una línea."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            entry.update(record.extra)
        return json.dumps(entry, ensure_ascii=False, default=str)


class StructuredLogger:
    """Wrapper alrededor de logging.Logger que emite JSON structurado."""

    def __init__(self, name: str, level: int = logging.INFO) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.handlers.clear()

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
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
