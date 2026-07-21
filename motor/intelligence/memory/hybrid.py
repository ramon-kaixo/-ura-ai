"""HybridMemory — combina vector + SQLite + FTS5 en una sola implementación.

Implementa MemoryStore combinando:
  - IVectorStore (Qdrant): búsqueda semántica por similitud de vectores
  - SQLite: metadatos estructurados y filtros exactos
  - FTS5: búsqueda por texto completo con ranking BM25

Uso:
    from motor.intelligence.memory.hybrid import HybridMemory
    from motor.core.qdrant_client import QdrantClient

    memory = HybridMemory(vector_store=QdrantClient(...), db_path="/tmp/hybrid.db")
    memory.store(MemoryRecord(text="...", metadata={}, vector=[...]))
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
    from pathlib import Path

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
    def __init__(self, vector_store: IVectorStore | None = None, db_path: str | Path = ":memory:") -> None:
        self._vector_store = vector_store
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.executescript(_SCHEMA)
        return self._conn

    def store(
        self,
        *,
        payload: str = "",
        memory_type: MemoryType = MemoryType.WORKING,
        metadata: dict[str, Any] | None = None,
        vector: list[float] | None = None,
    ) -> str:
        conn = self._get_conn()
        rid = uuid.uuid4().hex[:16]
        meta_str = json.dumps(metadata or {})
        with self._lock:
            conn.execute(
                "INSERT OR REPLACE INTO memory_metadata (id, memory_type, created_at, metadata) VALUES (?, ?, ?, ?)",
                (rid, memory_type.value, datetime.now(UTC).isoformat(), meta_str),
            )
            conn.execute(
                "INSERT OR REPLACE INTO memory_fts (id, text, metadata) VALUES (?, ?, ?)",
                (rid, payload, meta_str),
            )
            conn.commit()
        if self._vector_store and vector:
            self._vector_store.guardar_incidente({
                "id": rid,
                "vector": vector,
                "payload": {"text": payload[:500], "metadata": metadata},
            })
        return rid

    def search(
        self,
        query: str,
        k: int = 10,
        memory_type: MemoryType | None = None,
    ) -> list[MemoryRecord]:
        conn = self._get_conn()
        with self._lock:
            cursor = conn.execute(
                "SELECT m.id, m.memory_type, m.created_at, m.metadata, fts.text "
                "FROM memory_fts fts "
                "JOIN memory_metadata m ON m.id = fts.id "
                "WHERE memory_fts MATCH ? "
                + ("AND m.memory_type = ? " if memory_type else "")
                + "ORDER BY rank LIMIT ?",
                [query] + ([memory_type.value] if memory_type else []) + [k],
            )
            rows = cursor.fetchall()
        return [
            MemoryRecord(
                id=row[0],
                type=MemoryType(row[1]) if row[1] else MemoryType.WORKING,
                payload=row[4],
                metadata=json.loads(row[3]) if row[3] else {},
            )
            for row in rows
        ]

    def get(self, record_id: str) -> MemoryRecord | None:
        conn = self._get_conn()
        with self._lock:
            cursor = conn.execute(
                "SELECT m.id, m.memory_type, m.created_at, m.metadata, fts.text "
                "FROM memory_metadata m "
                "LEFT JOIN memory_fts fts ON fts.id = m.id "
                "WHERE m.id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        return MemoryRecord(
            id=row[0],
            type=MemoryType(row[1]) if row[1] else MemoryType.WORKING,
            payload=row[4] or "",
            metadata=json.loads(row[3]) if row[3] else {},
        )

    def delete(self, record_id: str) -> bool:
        conn = self._get_conn()
        with self._lock:
            cursor = conn.execute("DELETE FROM memory_metadata WHERE id = ?", (record_id,))
            conn.execute("DELETE FROM memory_fts WHERE id = ?", (record_id,))
            conn.commit()
        return cursor.rowcount > 0

    def count(self, memory_type: MemoryType | None = None) -> int:
        conn = self._get_conn()
        with self._lock:
            if memory_type:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM memory_metadata WHERE memory_type = ?",
                    [memory_type.value],
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM memory_metadata")
            return cursor.fetchone()[0]

    def health(self) -> dict[str, Any]:
        conn = self._get_conn()
        with self._lock:
            cursor = conn.execute("SELECT COUNT(*) FROM memory_metadata")
            total = cursor.fetchone()[0]
        vs_ok = True
        if self._vector_store:
            try:
                vs_ok = self._vector_store.buscar_similares([[0.0]], limite=1) is not None
            except Exception:
                vs_ok = False
        return {"total_records": total, "vector_store_ok": vs_ok}
