"""HybridMemory — combina vector + SQLite + FTS5 en una sola implementacion.

Implementa MemoryStore combinando:
  - IVectorStore (Qdrant): busqueda semantica por similitud de vectores
  - SQLite: metadatos estructurados y filtros exactos
  - FTS5: busqueda por texto completo con ranking BM25

Uso:
    from motor.intelligence.memory.hybrid import HybridMemory

    memory = HybridMemory(db_path="/tmp/hybrid.db")
    memory.store(payload="texto", metadata={"source": "test"})
    results = memory.search("consulta")
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from motor.intelligence.memory.record import MemoryRecord, MemoryType

if TYPE_CHECKING:
    from core.interfaces import IVectorStore

log = logging.getLogger("ura.memory.hybrid")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_metadata (
    id TEXT PRIMARY KEY,
    memory_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    id UNINDEXED,
    text,
    metadata,
    tokenize='porter unicode61'
);
"""


class HybridMemory:
    def __init__(self, vector_store: IVectorStore | None = None, db_path: str = ":memory:") -> None:
        self._vector_store = vector_store
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.executescript(_SCHEMA)
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    log.debug("error closing hybrid memory db", exc_info=True)
                finally:
                    self._conn = None

    def clear(self) -> None:
        """Elimina todos los registros de la base de datos en memoria."""
        conn = self._get_conn()
        try:
            with self._lock:
                conn.execute("DELETE FROM memory_metadata")
                conn.execute("DELETE FROM memory_fts")
                conn.commit()
        except Exception:
            log.exception("error clearing hybrid memory")

    def __enter__(self) -> HybridMemory:  # noqa: PYI034
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def store(
        self,
        payload: str = "",
        memory_type: MemoryType = MemoryType.WORKING,
        metadata: dict[str, Any] | None = None,
        vector: list[float] | None = None,
    ) -> str:
        conn = self._get_conn()
        rid = uuid.uuid4().hex
        meta_str = json.dumps(metadata or {})
        try:
            with self._lock:
                conn.execute(
                    "INSERT INTO memory_metadata (id, memory_type, created_at, metadata) VALUES (?, ?, ?, ?)",
                    (rid, memory_type.value, datetime.now(UTC).isoformat(), meta_str),
                )
                conn.execute(
                    "INSERT INTO memory_fts (id, text, metadata) VALUES (?, ?, ?)",
                    (rid, payload, meta_str),
                )
                conn.commit()
        except Exception:
            log.exception("Error storing in hybrid memory")
            raise

        if self._vector_store and vector:
            try:
                self._vector_store.guardar_incidente({
                    "ts": datetime.now(UTC).isoformat(),
                    "tipo": "MemoryRecord",
                    "resumen": payload[:500],
                    "impacto_memoria": vector,
                    "metadata": metadata or {},
                })
            except Exception:
                log.debug("vector store write failed", exc_info=True)
        return rid

    def search(
        self,
        query: str,
        k: int = 10,
        memory_type: MemoryType | None = None,
    ) -> list[MemoryRecord]:
        if not query or not query.strip():
            return []
        k = max(1, k)
        conn = self._get_conn()
        try:
            with self._lock:
                if memory_type:
                    cursor = conn.execute(
                        "SELECT m.id, m.memory_type, m.created_at, m.metadata, fts.text "
                        "FROM memory_fts fts JOIN memory_metadata m ON m.id = fts.id "
                        "WHERE fts.text MATCH ? AND m.memory_type = ? ORDER BY rank LIMIT ?",
                        (query, memory_type.value, k),
                    )
                else:
                    cursor = conn.execute(
                        "SELECT m.id, m.memory_type, m.created_at, m.metadata, fts.text "
                        "FROM memory_fts fts JOIN memory_metadata m ON m.id = fts.id "
                        "WHERE fts.text MATCH ? ORDER BY rank LIMIT ?",
                        (query, k),
                    )
                rows = cursor.fetchall()
        except sqlite3.OperationalError:
            log.warning("FTS5 search failed for query: %s", query[:100])
            return []

        results: list[MemoryRecord] = []
        for row in rows:
            try:
                mtype = MemoryType(row[1]) if row[1] else MemoryType.WORKING
            except ValueError:
                mtype = MemoryType.WORKING
            try:
                mdata = json.loads(row[3]) if row[3] else {}
            except (json.JSONDecodeError, TypeError):
                mdata = {}
            results.append(MemoryRecord(
                id=row[0],
                type=mtype,
                payload=row[4] or "",
                metadata=mdata,
            ))
        return results

    def get(self, record_id: str) -> MemoryRecord | None:
        conn = self._get_conn()
        try:
            with self._lock:
                cursor = conn.execute(
                    "SELECT m.id, m.memory_type, m.created_at, m.metadata, fts.text "
                    "FROM memory_metadata m LEFT JOIN memory_fts fts ON fts.id = m.id "
                    "WHERE m.id = ?",
                    (record_id,),
                )
                row = cursor.fetchone()
        except Exception:
            log.exception("Error getting record %s", record_id)
            return None
        if not row:
            return None
        try:
            mtype = MemoryType(row[1]) if row[1] else MemoryType.WORKING
        except ValueError:
            mtype = MemoryType.WORKING
        try:
            mdata = json.loads(row[3]) if row[3] else {}
        except (json.JSONDecodeError, TypeError):
            mdata = {}
        return MemoryRecord(
            id=row[0],
            type=mtype,
            payload=row[4] or "",
            metadata=mdata,
        )

    def delete(self, record_id: str) -> bool:
        conn = self._get_conn()
        try:
            with self._lock:
                cursor = conn.execute("DELETE FROM memory_metadata WHERE id = ?", (record_id,))
                conn.execute("DELETE FROM memory_fts WHERE id = ?", (record_id,))
                conn.commit()
            return cursor.rowcount > 0
        except Exception:
            log.exception("Error deleting record %s", record_id)
            return False

    def count(self, memory_type: MemoryType | None = None) -> int:
        conn = self._get_conn()
        try:
            with self._lock:
                if memory_type:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM memory_metadata WHERE memory_type = ?",
                        (memory_type.value,),
                    )
                else:
                    cursor = conn.execute("SELECT COUNT(*) FROM memory_metadata")
                return cursor.fetchone()[0]
        except Exception:
            log.exception("Error counting records")
            return 0

    def health(self) -> dict[str, Any]:
        total = 0
        try:
            total = self.count()
        except Exception:
            log.debug("health check count failed", exc_info=True)
        vs_ok = True
        if self._vector_store:
            try:
                vs_ok = self._vector_store.buscar_similares([0.0], limite=1) is not None
            except Exception:
                vs_ok = False
        return {"total_records": total, "vector_store_ok": vs_ok}
