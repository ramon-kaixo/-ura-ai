"""Queries — consultas estructuradas sobre memoria semántica.

Permite responder:
  ¿Qué objetivos ejecutó URA la semana pasada?
  ¿Qué plugin tarda más?
  ¿Qué decisiones se tomaron para un objetivo específico?
  ¿Cuál fue la tasa de éxito por tipo de pipeline?
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from scripts.pro.autonomy.memory.schema import migrate

if TYPE_CHECKING:
    from pathlib import Path


class SemanticQueries:
    """Consultas sobre la memoria semántica."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            migrate(self._conn, self._db_path)
        return self._conn

    def executions_by_pipeline(self, pipeline: str, limit: int = 20) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM executions WHERE pipeline = ? ORDER BY start_time DESC LIMIT ?",
            (pipeline, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def executions_by_date(self, days: int = 7) -> list[dict]:
        conn = self._connect()
        since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT * FROM executions WHERE start_time >= ? ORDER BY start_time DESC",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]

    def executions_by_goal(self, goal_title: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT e.* FROM executions e
               JOIN goals g ON g.execution_id = e.execution_id
               WHERE g.title LIKE ? ORDER BY e.start_time DESC""",
            (f"%{goal_title}%",),
        ).fetchall()
        return [dict(r) for r in rows]

    def plugin_stats(self, plugin_name: str) -> dict[str, Any]:
        conn = self._connect()
        row = conn.execute(
            """SELECT COUNT(*) as runs, AVG(duration_s) as avg_dur,
                      MAX(duration_s) as max_dur, MIN(duration_s) as min_dur,
                      SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) as errors
               FROM plugin_durations WHERE plugin_name = ?""",
            (plugin_name,),
        ).fetchone()
        return dict(row) if row else {}

    def slowest_plugins(self, limit: int = 10) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT plugin_name, COUNT(*) as runs,
                      ROUND(AVG(duration_s), 1) as avg_dur,
                      SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) as errors
               FROM plugin_durations
               GROUP BY plugin_name
               ORDER BY avg_dur DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def decisions_for_goal(self, goal_id: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT d.* FROM decisions d
               JOIN goals g ON g.execution_id = d.execution_id
               WHERE g.goal_id = ? ORDER BY d.timestamp""",
            (goal_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def promotion_rate(self) -> dict[str, Any]:
        conn = self._connect()
        row = conn.execute(
            """SELECT COUNT(*) as total,
                      SUM(promotion) as promoted,
                      ROUND(AVG(CAST(promotion AS REAL)) * 100, 1) as rate
               FROM executions""",
        ).fetchone()
        return dict(row) if row else {}

    def goals_by_status(self, status: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute("SELECT * FROM goals WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        return [dict(r) for r in rows]

    def total_size(self) -> dict[str, int]:
        conn = self._connect()
        return {
            "execuciones": conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0],
            "plugins": conn.execute("SELECT COUNT(*) FROM plugin_durations").fetchone()[0],
            "decisiones": conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0],
            "objetivos": conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0],
        }

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
