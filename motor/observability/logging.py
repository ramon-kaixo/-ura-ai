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
    json_output: bool = True,  # noqa: FBT001, FBT002
) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler()
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    root.handlers.clear()
    root.addHandler(handler)
    root.addFilter(ContextFilter())
