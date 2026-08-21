"""Fase 4: EpisodicMemory — eventos y resultados de pipelines."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("tuneladora.memory.episodic")


@dataclass(frozen=True)
class Episode:
    episode_id: str
    pipeline: str
    status: str
    started: str
    finished: str | None = None
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None


class EpisodicMemory:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    episode_id TEXT PRIMARY KEY,
                    pipeline TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    started TEXT NOT NULL,
                    finished TEXT,
                    summary TEXT DEFAULT '',
                    details TEXT DEFAULT '{}',
                    duration_ms REAL DEFAULT 0.0,
                    error TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ep_pipeline ON episodes(pipeline)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ep_status ON episodes(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ep_started ON episodes(started)
            """)
            conn.commit()

    def record(self, episode: Episode) -> None:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO episodes
                (episode_id, pipeline, status, started, finished, summary, details, duration_ms, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode.episode_id,
                    episode.pipeline,
                    episode.status,
                    episode.started,
                    episode.finished,
                    episode.summary,
                    json.dumps(episode.details),
                    episode.duration_ms,
                    episode.error,
                ),
            )
            conn.commit()
        log.debug("Episodio registrado: %s [%s]", episode.episode_id, episode.status)

    def get(self, episode_id: str) -> Episode | None:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT episode_id, pipeline, status, started, finished, summary, details, duration_ms, error "
                "FROM episodes WHERE episode_id = ?",
                (episode_id,),
            ).fetchone()
        if row is None:
            return None
        return Episode(
            episode_id=row[0],
            pipeline=row[1],
            status=row[2],
            started=row[3],
            finished=row[4],
            summary=row[5],
            details=json.loads(row[6]),
            duration_ms=row[7],
            error=row[8],
        )

    def list_recent(self, pipeline: str | None = None, limit: int = 20) -> list[Episode]:
        if pipeline:
            rows = self._query(
                "SELECT * FROM episodes WHERE pipeline = ? ORDER BY started DESC LIMIT ?",
                (pipeline, limit),
            )
        else:
            rows = self._query(
                "SELECT * FROM episodes ORDER BY started DESC LIMIT ?",
                (limit,),
            )
        return [self._row_to_episode(r) for r in rows]

    def list_failures(self, pipeline: str | None = None, since: str | None = None, limit: int = 20) -> list[Episode]:
        clauses = ["status = 'failed'"]
        params: list[Any] = []
        if pipeline:
            clauses.append("pipeline = ?")
            params.append(pipeline)
        if since:
            clauses.append("started >= ?")
            params.append(since)
        where = " AND ".join(clauses)
        rows = self._query(
            f"SELECT * FROM episodes WHERE {where} ORDER BY started DESC LIMIT ?",  # noqa: S608
            (*params, limit),
        )
        return [self._row_to_episode(r) for r in rows]

    def count_failures(self, pipeline: str | None = None, since_hours: int = 24) -> int:
        import time

        since = datetime.fromtimestamp(time.time() - since_hours * 3600, tz=UTC).isoformat()
        clauses = ["status = 'failed'", "started >= ?"]
        params: list[Any] = [since]
        if pipeline:
            clauses.append("pipeline = ?")
            params.append(pipeline)
        where = " AND ".join(clauses)
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            return conn.execute(
                f"SELECT COUNT(*) FROM episodes WHERE {where}",  # noqa: S608 - filtros internos fijos
                params,
            ).fetchone()[0]

    def delete_old(self, before: str) -> int:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            cur = conn.execute("DELETE FROM episodes WHERE started < ?", (before,))
            conn.commit()
            return cur.rowcount

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        with self._lock, sqlite3.connect(str(self._db_path)) as conn:
            return conn.execute(sql, params).fetchall()

    @staticmethod
    def _row_to_episode(row: Any) -> Episode:
        return Episode(
            episode_id=row[0],
            pipeline=row[1],
            status=row[2],
            started=row[3],
            finished=row[4],
            summary=row[5],
            details=json.loads(row[6]),
            duration_ms=row[7],
            error=row[8],
        )
