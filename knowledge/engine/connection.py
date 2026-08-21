"""Connection factory — única fuente de conexiones SQLite.

TODA conexión a la knowledge DB debe pasar por open_db().
Prohibido crear conexiones con sqlite3.connect() directamente.

PRAGMAs obligatorios:
  - journal_mode=WAL          → lectores no bloquean escritores
  - foreign_keys=ON           → integridad referencial
  - synchronous=NORMAL        → equilibrio durabilidad/rendimiento
  - journal_size_limit=64MB   → WAL no crece indefinido
  - busy_timeout=5000         → espera 5s ante SQLITE_BUSY

row_factory = sqlite3.Row para todas las conexiones.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("ura.knowledge.connection")

_BUSY_RETRY_MS = 50
_BUSY_TIMEOUT_S = 5.0


def open_db(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA journal_size_limit=67108864")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def begin_immediate(
    conn: sqlite3.Connection,
    timeout: float = _BUSY_TIMEOUT_S,
) -> None:
    """BEGIN IMMEDIATE con reintento ante SQLITE_BUSY.

    SQLite en WAL mode puede lanzar SQLITE_BUSY si otro escritor
    está activo. Esta función reintenta hasta *timeout* segundos.

    Raises sqlite3.OperationalError si no se pudo adquirir el lock.
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            conn.execute("BEGIN IMMEDIATE")
            return
        except sqlite3.OperationalError as e:
            if "database is locked" not in str(e):
                raise
            _inc_busy_retry()
            if time.monotonic() >= deadline:
                msg = f"Could not acquire BEGIN IMMEDIATE after {timeout}s"
                raise sqlite3.OperationalError(msg) from e
            time.sleep(_BUSY_RETRY_MS / 1000.0)


def _inc_busy_retry() -> None:
    """Incrementa el contador de reintentos SQLITE_BUSY (best effort)."""
    try:
        from knowledge.engine.metrics import sqlite_busy_retries_total

        sqlite_busy_retries_total.inc()
    except Exception:  # noqa: S110
        pass
