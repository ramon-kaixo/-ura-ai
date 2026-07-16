"""Audit backend protocol — contrato para backends de auditoría.

Principios:
  - write() es best effort: nunca raise, solo log + métrica.
  - flush() garantiza persistencia al backend.
  - health_check() retorna estado sin excepciones.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from knowledge.engine.models import AuditEvent

log = logging.getLogger("ura.knowledge.audit")


@dataclass
class AuditHealth:
    """Estado de salud de un backend de auditoría."""

    healthy: bool = True
    error: str = ""
    events_written: int = 0
    events_ingested: int = 0
    last_error: str = ""


class AuditBackend(Protocol):
    """Contrato para backends de auditoría.

    write() debe ser best effort: nunca raise.
    flush() garantiza persistencia (no-op en NDJSON, commit en SQLite).
    health_check() retorna estado sin excepciones.
    """

    def write(self, event: AuditEvent) -> None: ...
    def flush(self) -> None: ...
    def health_check(self) -> AuditHealth: ...


def record_metric() -> None:
    """Incrementa el contador de fallos de escritura de auditoría."""
    try:
        from knowledge.engine.metrics import audit_write_failures

        audit_write_failures.inc()
    except Exception:
        pass
