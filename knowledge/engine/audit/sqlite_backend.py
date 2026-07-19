"""SQLite audit backend — escritura directa a op_audit.

NO usar en read path. Solo para ingesta batch desde NDJSON
o para procesos que ya tienen una transacción SQLite abierta.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from knowledge.engine.audit.backend import AuditHealth, record_metric

if TYPE_CHECKING:
    from pathlib import Path

    from knowledge.engine.models import AuditEvent

log = logging.getLogger("ura.knowledge.audit.sqlite")


class SQLiteAuditBackend:
    """Backend SQLite — cada write() hace commit inmediato."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._events_written = 0
        self._last_error = ""

    def write(self, event: AuditEvent) -> None:
        from knowledge.engine.connection import begin_immediate, open_db

        try:
            conn = open_db(self._db_path)
            begin_immediate(conn)
            conn.execute(
                "INSERT INTO op_audit "
                "(action, actor, entity_type, entity_id, result, "
                " correlation_id, timestamp, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.action,
                    event.actor,
                    event.entity_type,
                    event.entity_id,
                    event.result,
                    event.correlation_id,
                    event.timestamp,
                    json.dumps(event.metadata),
                ),
            )
            conn.commit()
            conn.close()
            self._events_written += 1
        except Exception as exc:
            self._last_error = str(exc)
            log.warning("Audit SQLite write failed: %s", exc)
            record_metric()

    def flush(self) -> None:
        pass

    def health_check(self) -> AuditHealth:
        return AuditHealth(
            healthy=True,
            events_written=self._events_written,
            last_error=self._last_error,
        )
