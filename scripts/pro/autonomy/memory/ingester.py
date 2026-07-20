"""Ingester — lee el ExecutionLedger y lo transforma a SQLite semántico.

Procesa cada archivo JSON del ledger y lo inserta en las tablas SQLite.
Es idempotente: si una execution_id ya existe, la salta.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from scripts.pro.autonomy.memory.schema import migrate


class LedgerIngester:
    """Ingiere el ExecutionLedger en SQLite semántico."""

    def __init__(self, db_path: Path, nervioso: Path) -> None:
        self._db_path = db_path
        self._ledger_dir = nervioso / "ledger"
        self._conn: sqlite3.Connection | None = None
        self._stats = {"procesados": 0, "omitidos": 0, "errores": 0}

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            migrate(self._conn, self._db_path)
        return self._conn

    def _execution_exists(self, execution_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM executions WHERE execution_id = ?", (execution_id,)
        ).fetchone()
        return row is not None

    def _ingest_execution(self, entry: dict) -> None:
        eid = entry.get("execution_id", "")
        if self._execution_exists(eid):
            self._stats["omitidos"] += 1
            return

        conn = self._conn
        # executions
        conn.execute(
            """INSERT OR IGNORE INTO executions
               (execution_id, pipeline, engine_version, start_time, end_time,
                duration_ms, result, promotion, rollback, host,
                git_commit_before, git_commit_after,
                changed_files, changed_lines, plugins_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                eid,
                entry.get("pipeline", ""),
                entry.get("engine_version", ""),
                entry.get("start_time", ""),
                entry.get("end_time", ""),
                entry.get("duration_ms", 0),
                entry.get("result", ""),
                1 if entry.get("promotion") else 0,
                1 if entry.get("rollback") else 0,
                entry.get("host", ""),
                entry.get("git_commit_before", ""),
                entry.get("git_commit_after", ""),
                entry.get("changed_files", 0),
                entry.get("changed_lines", 0),
                len(entry.get("plugins_activated", [])),
            ),
        )

        # goals
        goal = entry.get("goal") or {}
        if isinstance(goal, dict) and goal.get("goal_id"):
            conn.execute(
                """INSERT OR IGNORE INTO goals
                   (goal_id, execution_id, title, priority, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    goal["goal_id"], eid,
                    goal.get("title", ""), goal.get("priority", ""),
                    goal.get("status", ""), goal.get("created_at", ""),
                ),
            )

        # plugin_durations
        for p, d in (entry.get("plugin_durations") or {}).items():
            status = (entry.get("plugin_status") or {}).get(p, "")
            conn.execute(
                """INSERT INTO plugin_durations
                   (execution_id, plugin_name, duration_s, status)
                   VALUES (?, ?, ?, ?)""",
                (eid, p, d, status),
            )

        # decisions
        for dec in entry.get("decisions", []):
            conn.execute(
                """INSERT INTO decisions
                   (execution_id, decision_type, details, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (eid, dec.get("type", ""), json.dumps(dec), dec.get("timestamp", "")),
            )

        self._stats["procesados"] += 1

    def ingest(self, max_entries: int = 0) -> dict:
        """Ingiere todas las entradas del ledger no procesadas."""
        if not self._ledger_dir.exists():
            self._stats["errores"] = 1
            return dict(self._stats)

        conn = self._connect()
        processed = 0
        for f in sorted(self._ledger_dir.glob("*.json")):
            if max_entries and processed >= max_entries:
                break
            try:
                entry = json.loads(f.read_text(encoding="utf-8"))
                self._ingest_execution(entry)
                processed += 1
            except (json.JSONDecodeError, OSError, sqlite3.Error) as e:
                self._stats["errores"] += 1

        conn.commit()
        return dict(self._stats)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
