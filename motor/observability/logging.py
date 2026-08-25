"""Logging estructurado JSON — formateador, correlación, contexto."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import UTC, datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    def __init__(self, **defaults: Any) -> None:
        super().__init__()
        self._defaults = defaults

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update(self._defaults)

        if record.exc_info and record.exc_info[0]:
            entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        extra_keys = getattr(record, "extra_keys", None) or {}
        if isinstance(extra_keys, dict):
            entry.update(extra_keys)

        return json.dumps(entry, default=str, ensure_ascii=False)


_context = threading.local()


def set_correlation_id(cid: str | None = None) -> str:
    cid = cid or uuid.uuid4().hex[:12]
    _context.correlation_id = cid
    return cid


def get_correlation_id() -> str:
    return getattr(_context, "correlation_id", "")


def set_workflow_id(wid: str) -> None:
    _context.workflow_id = wid


def get_workflow_id() -> str:
    return getattr(_context, "workflow_id", "")


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        extra: dict[str, Any] = {}
        cid = get_correlation_id()
        if cid:
            extra["correlation_id"] = cid
        wid = get_workflow_id()
        if wid:
            extra["workflow_id"] = wid
        record.extra_keys = extra
        return True


def setup_logging(
    level: str = "INFO",
    json_output: bool = True,
    fmt: str | None = None,
    handlers: list[logging.Handler] | None = None,
    force: bool = True,
) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if force:
        root.handlers.clear()
        root.filters.clear()

    if handlers:
        for h in handlers:
            root.addHandler(h)
    else:
        handler = logging.StreamHandler()
        if fmt:
            handler.setFormatter(logging.Formatter(fmt))
        elif json_output:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)

    root.addFilter(ContextFilter())


class StructuredLogger:
    """Wrapper around logging.Logger that emits structured JSON.

    Deprecated: Use motor.observability.logging.StructuredLogger directly or plain logging.
    """

    def __init__(self, name: str, level: int = logging.INFO) -> None:
        import warnings

        warnings.warn(
            "StructuredLogger is deprecated. Use motor.observability.logging.StructuredLogger.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.handlers.clear()

        handler = logging.StreamHandler()
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
