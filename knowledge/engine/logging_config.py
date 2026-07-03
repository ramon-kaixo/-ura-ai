"""Logging configuration — logs estructurados opcionales + correlation_id.

URA_STRUCTURED_LOGS=true → output JSON con timestamp, level, logger, message,
correlation_id (si está disponible en el contexto).

URA_STRUCTURED_LOGS=false | unset → formato actual (sin cambios).

Uso:

    from knowledge.engine.logging_config import setup_logging, set_correlation_id

    setup_logging()

    set_correlation_id("abc123")
    logger.info("Esto aparece como JSON si URA_STRUCTURED_LOGS=true")

El correlation_id se propaga via threading.local, no por argumentos.
Se establece en request_compile() y perdura mientras dure la petición.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

_log_context = threading.local()


def set_correlation_id(cid: str) -> None:
    """Establece el correlation_id para el hilo actual."""
    _log_context.correlation_id = cid


def get_correlation_id() -> str:
    """Retorna el correlation_id del hilo actual, o '' si no está establecido."""
    return getattr(_log_context, "correlation_id", "")


class CorrelationFilter(logging.Filter):
    """Añade correlation_id a todos los LogRecord del hilo actual."""

    def filter(self, record: logging.LogRecord) -> bool:
        cid = get_correlation_id()
        record.correlation_id = cid or ""
        return True


class JSONFormatter(logging.Formatter):
    """Formatea logs como JSON.

    Campos: timestamp, level, logger, message, correlation_id, extra.
    """

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = getattr(record, "correlation_id", "")
        if cid:
            data["correlation_id"] = cid
        if record.exc_info and record.exc_info[0]:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging() -> None:
    """Configura el logging del Knowledge Engine.

    - Lee URA_STRUCTURED_LOGS del entorno.
    - Si es 'true' → JSONFormatter con CorrelationFilter.
    - Si no → mantiene la configuración existente (no toca handlers).
    """
    structured = os.environ.get("URA_STRUCTURED_LOGS", "").strip().lower()
    if structured != "true":
        return

    root = logging.getLogger()
    # No duplicar filtros/formatters si ya está configurado
    for handler in root.handlers:
        already_json = any(
            isinstance(fmt, JSONFormatter) for fmt in [handler.formatter]
        )
        if already_json:
            return

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.addFilter(CorrelationFilter())

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
