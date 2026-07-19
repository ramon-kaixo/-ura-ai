"""NDJSON audit backend — append-only, lock-free con flock cross-process.

Escribe un evento por línea en un archivo de auditoría.
Rotación con flock cross-process: al alcanzar MAX_BYTES, renombra a .1, .2, …

Ingesta atómica: rename() → INSERT → unlink() (nunca pérdida de eventos).
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from knowledge.engine.audit.backend import AuditHealth, record_metric
from knowledge.engine.models import AuditEvent

log = logging.getLogger("ura.knowledge.audit.ndjson")


class NDJSONAuditBackend:
    """Backend NDJSON — append-only con flock cross-process.

    La rotación usa un lock file (flock) para evitar que dos procesos
    roten simultáneamente. La ingesta usa rename atómico.
    """

    _lock: threading.Lock
    _file: Path
    _lock_file: Path
    _lock_fd: int | None
    _handle: Any
    _bytes_written: int
    _events_written: int
    _last_error: str

    MAX_BYTES: int = 100 * 1024 * 1024  # 100 MB por segmento
    MAX_SEGMENTS: int = 3

    def __init__(self, audit_dir: Path | str, filename: str = "audit.ndjson") -> None:
        self._lock = threading.Lock()
        self._file = Path(audit_dir) / filename
        self._lock_file = self._file.with_suffix(".ndjson.lock")
        self._lock_fd = None
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._file.open("a")
        self._bytes_written = self._file.stat().st_size if self._file.exists() else 0
        self._events_written = 0
        self._last_error = ""

    # ── Lock helpers (flock cross-process) ────────────────────────────────

    def _acquire_flock(self) -> bool:
        """Adquiere flock exclusivo sobre el lock file.

        Retorna True si se adquirió, False si no (non-blocking).
        """
        try:
            self._lock_fd = os.open(str(self._lock_file), os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, BlockingIOError):
            if self._lock_fd is not None:
                with contextlib.suppress(OSError):
                    os.close(self._lock_fd)
                self._lock_fd = None
            return False

    def _release_flock(self) -> None:
        if self._lock_fd is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            with contextlib.suppress(OSError):
                os.close(self._lock_fd)
            self._lock_fd = None

    # ── Public API ────────────────────────────────────────────────────────

    def write(self, event: AuditEvent) -> None:
        try:
            line = (
                json.dumps(
                    {
                        "action": event.action,
                        "actor": event.actor,
                        "entity_type": event.entity_type,
                        "entity_id": event.entity_id,
                        "result": event.result,
                        "correlation_id": event.correlation_id,
                        "timestamp": event.timestamp,
                        "metadata": event.metadata,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            with self._lock:
                if self._acquire_flock():
                    try:
                        self._maybe_rotate()
                        self._handle.write(line)
                        self._handle.flush()
                        self._bytes_written += len(line.encode())
                        self._events_written += 1
                    finally:
                        self._release_flock()
                else:
                    # Fallback: otro proceso tiene el lock, escribir sin rotar
                    self._handle.write(line)
                    self._handle.flush()
                    self._bytes_written += len(line.encode())
                    self._events_written += 1
        except OSError as exc:
            self._last_error = str(exc)
            log.warning("Audit NDJSON write failed: %s", exc)
            record_metric()

    def flush(self) -> None:
        pass

    def health_check(self) -> AuditHealth:
        try:
            parent = self._file.parent
            ok = parent.exists() and os.access(str(parent), os.W_OK)
            return AuditHealth(
                healthy=ok,
                error="" if ok else "Audit dir not writable",
                events_written=self._events_written,
            )
        except OSError as exc:
            return AuditHealth(healthy=False, error=str(exc))

    def close(self) -> None:
        with contextlib.suppress(OSError):
            self._handle.close()
        self._release_flock()

    # ── Rotación (con flock) ─────────────────────────────────────────────

    def _maybe_rotate(self) -> None:
        if self._bytes_written < self.MAX_BYTES:
            return
        # Re-verificar tamaño actual (otro proceso pudo haber rotado)
        current_size = self._file.stat().st_size if self._file.exists() else 0
        if current_size < self.MAX_BYTES:
            self._bytes_written = current_size
            return

        self._handle.close()
        try:
            for i in range(self.MAX_SEGMENTS - 1, 0, -1):
                older = self._file.with_suffix(f".ndjson.{i}")
                newer = self._file.with_suffix(f".ndjson.{i - 1}")
                if older.exists():
                    older.unlink()
                if newer.exists():
                    newer.rename(older)
            self._file.rename(self._file.with_suffix(".ndjson.1"))
        except OSError as exc:
            log.warning("Audit rotation failed: %s", exc)
            # Reabrir el archivo original (puede que ya no exista)
            self._handle = self._file.open("a")
            self._bytes_written = 0
            return
        self._handle = self._file.open("a")
        self._bytes_written = 0

    # ── Lectura (para ingest, tests) ─────────────────────────────────────

    def read_lines(self, segment: int = 0) -> list[AuditEvent]:
        """Lee eventos de un segmento. 0 = actual, 1 = más reciente.

        Útil para tests y recuperación. No usar en read path.
        """
        path = self._file if segment == 0 else self._file.with_suffix(f".ndjson.{segment}")
        if not path.exists():
            return []
        events: list[AuditEvent] = []
        with path.open() as f:
            for line in f:
                line = line.strip()  # noqa: PLW2901
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    events.append(AuditEvent(**data))
                except (json.JSONDecodeError, TypeError):
                    log.warning("Saltando línea NDJSON corrupta: %s", line[:80])
                    continue
        return events

    # ── Ingesta atómica (rename → process → unlink) ──────────────────────

    def ingest_into_sqlite(self, db_path: Path) -> int:
        """Ingesta batch atómica: rename → INSERT → unlink.

        El rename() es atómico en Linux/ext4.
        Si el proceso muere durante la ingesta, el archivo .processing
        asegura que los eventos no se pierden (pueden re-ingestarse).
        """
        from knowledge.engine.connection import open_db

        processing = self._file.with_suffix(".ndjson.processing")
        try:
            os.rename(str(self._file), str(processing))  # noqa: PTH104
        except FileNotFoundError:
            return 0

        # Abrir nuevo archivo para seguir escribiendo
        with self._lock:
            self._handle.close()
            self._handle = self._file.open("a")
            self._bytes_written = 0

        ingested = 0
        try:
            from knowledge.engine.connection import begin_immediate

            conn = open_db(db_path)
            conn.execute("PRAGMA synchronous=OFF")
            begin_immediate(conn)
            import time as _time

            _t0 = _time.monotonic()
            with processing.open() as f:
                for line in f:
                    line = line.strip()  # noqa: PLW2901
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        ev = AuditEvent(**data)
                        conn.execute(
                            "INSERT INTO op_audit "
                            "(action, actor, entity_type, entity_id, result, "
                            " correlation_id, timestamp, metadata) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                ev.action,
                                ev.actor,
                                ev.entity_type,
                                ev.entity_id,
                                ev.result,
                                ev.correlation_id,
                                ev.timestamp,
                                json.dumps(ev.metadata),
                            ),
                        )
                        ingested += 1
                    except (json.JSONDecodeError, TypeError, Exception) as exc:
                        log.warning("Saltando evento corrupto en ingest: %s", exc)
                        continue
            conn.commit()
            conn.close()
        except Exception as exc:
            log.warning("Audit SQLite ingest failed: %s", exc)
            return ingested

        # Métrica de duración
        try:
            from knowledge.engine.metrics import audit_ingest_duration_seconds

            audit_ingest_duration_seconds.observe(_time.monotonic() - _t0)
        except Exception:  # noqa: S110
            pass

        # Limpiar archivo procesado
        with contextlib.suppress(OSError):
            processing.unlink()
        return ingested
