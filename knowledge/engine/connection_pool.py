"""Connection pool — reutilización de conexiones SQLite solo lectura.

El Reader abría una conexión SQLite por cada búsqueda (100 conexiones para
100 búsquedas). Este pool reutiliza hasta N conexiones, reduciendo overhead.

Uso:
    pool = ReadConnectionPool(db_path, max_connections=5)
    conn = pool.acquire()
    try:
        rows = conn.execute("SELECT ...")
    finally:
        pool.release(conn)
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

log = logging.getLogger("ura.knowledge.connection_pool")


class ReadConnectionPool:
    """Pool de conexiones SQLite solo lectura.

    Las conexiones se crean bajo demanda hasta max_connections.
    Una vez alcanzado el límite, acquire() bloquea hasta que una
    conexión esté disponible.

    Todas las conexiones usan WAL mode (no bloquean escritores).
    """

    def __init__(self, db_path: Path, max_connections: int = 5) -> None:
        self._db_path = db_path
        self._max = max_connections
        self._lock = threading.Lock()
        self._pool: list[sqlite3.Connection] = []
        self._active = 0
        self._available = threading.Condition(self._lock)

    def acquire(self) -> sqlite3.Connection:
        """Obtiene una conexión del pool (bloqueante si todas en uso)."""
        with self._lock:
            while True:
                if self._pool:
                    conn = self._pool.pop()
                    self._active += 1
                    return conn
                if self._active < self._max:
                    conn = self._new_connection()
                    self._active += 1
                    return conn
                # Todas en uso, esperar
                self._available.wait()

    def release(self, conn: sqlite3.Connection) -> None:
        """Devuelve una conexión al pool."""
        with self._lock:
            self._pool.append(conn)
            self._active -= 1
            self._available.notify()

    def close_all(self) -> None:
        """Cierra todas las conexiones del pool."""
        with self._lock:
            for conn in self._pool:
                with contextlib.suppress(Exception):
                    conn.close()
            self._pool.clear()
            self._active = 0

    def _new_connection(self) -> sqlite3.Connection:
        from knowledge.engine.connection import open_db

        return open_db(self._db_path)

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active

    @property
    def idle_count(self) -> int:
        with self._lock:
            return len(self._pool)
