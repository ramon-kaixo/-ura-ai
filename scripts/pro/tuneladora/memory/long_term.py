"""Fase 3: LongTermMemory — persistencia SQLite de resultados."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("tuneladora.memory.long_term")


@dataclass(frozen=True)
class LTMEntry:
    key: str
    value: dict[str, Any]
    source: str
    created: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    tags: tuple[str, ...] = ()


class LongTermMemory:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ltm_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '[]',
                    created TEXT NOT NULL,
                    updated TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ltm_source ON ltm_store(source)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ltm_created ON ltm_store(created)
            """)
            conn.commit()

    def store(self, entry: LTMEntry) -> None:
        now = datetime.now(UTC).isoformat()
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ltm_store (key, value, source, tags, created, updated)
                VALUES (?, ?, ?, ?, COALESCE((SELECT created FROM ltm_store WHERE key = ?), ?), ?)
                """,
                (
                    entry.key, json.dumps(entry.value), entry.source,
                    json.dumps(list(entry.tags)), entry.key, entry.created, now,
                ),
            )
            conn.commit()
        log.debug("LTM stored %s", entry.key)

    def retrieve(self, key: str) -> LTMEntry | None:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT key, value, source, tags, created FROM ltm_store WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return LTMEntry(
            key=row[0],
            value=json.loads(row[1]),
            source=row[2],
            tags=tuple(json.loads(row[3])),
            created=row[4],
        )

    def search(self, *, source: str | None = None, tag: str | None = None, limit: int = 100) -> list[LTMEntry]:
        clauses: list[str] = []
        params: list[Any] = []
        if source:
            clauses.append("source = ?")
            params.append(source)
        if tag:
            clauses.append("tags LIKE ?")
            params.append(f"%{json.dumps(tag)}%")
        where = " AND ".join(clauses) if clauses else "1=1"
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            rows = conn.execute(
                f"SELECT key, value, source, tags, created FROM ltm_store WHERE {where} ORDER BY created DESC LIMIT ?",  # noqa: S608
                (*params, limit),
            ).fetchall()
        return [
            LTMEntry(key=r[0], value=json.loads(r[1]), source=r[2], tags=tuple(json.loads(r[3])), created=r[4])
            for r in rows
        ]

    def delete(self, key: str) -> bool:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            cur = conn.execute("DELETE FROM ltm_store WHERE key = ?", (key,))
            conn.commit()
            return cur.rowcount > 0

    def count(self) -> int:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            return conn.execute("SELECT COUNT(*) FROM ltm_store").fetchone()[0]

    def vacuum(self) -> None:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("VACUUM")
            log.info("LTM vacuum completado")

    def close(self) -> None:
        pass
