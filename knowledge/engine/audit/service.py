"""AuditService — facade de auditoría para el resto del Knowledge Engine.

El resto del proyecto (Reader, Compiler, Archiver, CLI) solo conoce
esta clase. Nunca accede directamente al backend.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from knowledge.engine.audit.ndjson_backend import NDJSONAuditBackend
from knowledge.engine.models import AuditEvent

if TYPE_CHECKING:
    from knowledge.engine.audit.backend import AuditBackend

log = logging.getLogger("ura.knowledge.audit.service")


class AuditService:
    """Facade de auditoría.

    Uso:
        audit = AuditService(backend)
        audit.log_read(query="foo", docs=2, cid="abc")
    """

    def __init__(self, backend: AuditBackend | None = None) -> None:
        self._backend = backend

    @property
    def backend(self) -> AuditBackend | None:
        return self._backend

    @backend.setter
    def backend(self, value: AuditBackend | None) -> None:
        self._backend = value

    def log_read(
        self,
        query: str = "",
        docs: int = 0,
        correlation_id: str = "",
        **extra: Any,
    ) -> None:
        if self._backend is None:
            return
        self._backend.write(
            AuditEvent(
                action="search",
                actor="reader",
                entity_type="graph",
                entity_id=query[:64] or "-",
                result="success",
                correlation_id=correlation_id,
                timestamp=datetime.now(UTC).isoformat(),
                metadata={"docs_returned": docs, **extra},
            ),
        )

    def log_compile(
        self,
        result: str = "success",
        correlation_id: str = "",
        **extra: Any,
    ) -> None:
        if self._backend is None:
            return
        self._backend.write(
            AuditEvent(
                action="compile",
                actor="compiler",
                entity_type="graph",
                entity_id=correlation_id[:16] or "-",
                result=result,
                correlation_id=correlation_id,
                timestamp=datetime.now(UTC).isoformat(),
                metadata=extra,
            ),
        )

    def log_archive(
        self,
        kind: str = "source",
        result: str = "success",
        correlation_id: str = "",
        **extra: Any,
    ) -> None:
        if self._backend is None:
            return
        self._backend.write(
            AuditEvent(
                action="archive",
                actor="archiver",
                entity_type="archive",
                entity_id=f"{kind}-{correlation_id[:8]}" if correlation_id else kind,
                result=result,
                correlation_id=correlation_id,
                timestamp=datetime.now(UTC).isoformat(),
                metadata=extra,
            ),
        )

    def log(
        self,
        action: str,
        actor: str,
        entity_type: str,
        entity_id: str,
        result: str = "success",
        correlation_id: str = "",
        **extra: Any,
    ) -> None:
        if self._backend is None:
            return
        self._backend.write(
            AuditEvent(
                action=action,
                actor=actor,
                entity_type=entity_type,
                entity_id=entity_id,
                result=result,
                correlation_id=correlation_id,
                timestamp=datetime.now(UTC).isoformat(),
                metadata=extra,
            ),
        )

    def ingest(self, db_path: Path) -> int:
        """Ingesta batch NDJSON → op_audit.

        Retorna número de eventos ingestados.
        Solo tiene efecto si el backend es NDJSONAuditBackend.
        """
        if not isinstance(self._backend, NDJSONAuditBackend):
            return 0
        return self._backend.ingest_into_sqlite(db_path)

    def close(self) -> None:
        if isinstance(self._backend, NDJSONAuditBackend):
            self._backend.close()


# ── Singleton global ──────────────────────────────────────────────────────

_AUDIT_INSTANCE: AuditService | None = None
_AUDIT_LOCK = threading.Lock()


def get_audit() -> AuditService:
    """Retorna la instancia global de AuditService.

    Si no existe y no se puede crear el backend por defecto,
    retorna un AuditService sin backend (no-op).
    """
    global _AUDIT_INSTANCE  # noqa: PLW0603
    if _AUDIT_INSTANCE is not None:
        return _AUDIT_INSTANCE
    with _AUDIT_LOCK:
        if _AUDIT_INSTANCE is not None:
            return _AUDIT_INSTANCE
        try:
            audit_dir = Path.home() / ".ura" / "audit"
            backend = NDJSONAuditBackend(audit_dir)
            _AUDIT_INSTANCE = AuditService(backend)
        except (OSError, PermissionError):
            _AUDIT_INSTANCE = AuditService()
            log.warning("No se pudo crear audit backend — modo no-op")
        return _AUDIT_INSTANCE


def set_audit(audit: AuditService) -> None:
    """Establece la instancia global (útil en tests)."""
    global _AUDIT_INSTANCE  # noqa: PLW0603
    _AUDIT_INSTANCE = audit
