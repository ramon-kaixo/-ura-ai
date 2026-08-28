"""Telemetry — Metricas operativas del orquestador.

Almacena eventos en SQLite (WAL mode) para dashboard y auditoria.
Sin dependencias externas: solo stdlib + sqlite3.

Eventos:
  - task_created, task_assigned, task_started, task_completed, task_failed, task_timeout
  - gate_pass, gate_fail
  - audit_start, audit_end
  - merge_ok, merge_fail
  - proxy_fallback, proxy_success
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent.parent / "data" / "telemetry.db"


@dataclass(frozen=True)
class Metric:
    """Un solo evento de telemetria."""

    id: int
    ts: str
    event: str
    task_id: str
    details: str
    node: str


class TelemetryStore:
    """Almacen SQLite de metricas operativas."""

    def __init__(self, db_path: Path | str = _DEFAULT_DB) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._open_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    event TEXT NOT NULL,
                    task_id TEXT NOT NULL DEFAULT '',
                    details TEXT NOT NULL DEFAULT '{}',
                    node TEXT NOT NULL DEFAULT 'unknown'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event ON metrics(event)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON metrics(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task ON metrics(task_id)")

    @contextmanager
    def _open_db(self) -> Any:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def record(
        self,
        event: str,
        task_id: str = "",
        details: dict[str, Any] | None = None,
        node: str = "unknown",
    ) -> None:
        """Registra un evento de telemetria."""
        now = datetime.now(UTC).isoformat()
        details_str = json.dumps(details or {})

        with self._lock, self._open_db() as conn:
            conn.execute(
                "INSERT INTO metrics (ts, event, task_id, details, node) VALUES (?, ?, ?, ?, ?)",
                (now, event, task_id, details_str, node),
            )

    def query(
        self,
        event: str | None = None,
        task_id: str | None = None,
        since_minutes: int | None = None,
        limit: int = 100,
    ) -> list[Metric]:
        """Consulta metricas con filtros opcionales."""
        clauses: list[str] = []
        params: list[Any] = []

        if event:
            clauses.append("event = ?")
            params.append(event)
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if since_minutes:
            clauses.append("ts >= datetime('now', ? || ' minutes')")
            params.append(f"-{since_minutes}")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT id, ts, event, task_id, details, node FROM metrics {where} ORDER BY id DESC LIMIT ?"  # noqa: S608  # nosec B608
        params.append(limit)

        with self._open_db() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [Metric(id=r[0], ts=r[1], event=r[2], task_id=r[3], details=r[4], node=r[5]) for r in rows]

    def stats(self, since_minutes: int = 60) -> dict[str, Any]:
        """Resumen de metricas para el dashboard."""
        with self._open_db() as conn:
            # Total events in window
            row = conn.execute(
                "SELECT COUNT(*) FROM metrics WHERE ts >= datetime('now', ? || ' minutes')",
                (f"-{since_minutes}",),
            ).fetchone()
            total = row[0] if row else 0

            # By event type
            rows = conn.execute(
                "SELECT event, COUNT(*) as cnt FROM metrics "
                "WHERE ts >= datetime('now', ? || ' minutes') "
                "GROUP BY event ORDER BY cnt DESC",
                (f"-{since_minutes}",),
            ).fetchall()
            by_event = {r[0]: r[1] for r in rows}

            # By node
            rows = conn.execute(
                "SELECT node, COUNT(*) as cnt FROM metrics "
                "WHERE ts >= datetime('now', ? || ' minutes') "
                "GROUP BY node ORDER BY cnt DESC",
                (f"-{since_minutes}",),
            ).fetchall()
            by_node = {r[0]: r[1] for r in rows}

            # Tasks completed vs failed
            completed = by_event.get("task_completed", 0)
            failed = by_event.get("task_failed", 0) + by_event.get("task_timeout", 0)
            success_rate = round(completed / (completed + failed) * 100, 1) if (completed + failed) > 0 else 100.0

            # Gate pass/fail
            gate_pass = by_event.get("gate_pass", 0)
            gate_fail = by_event.get("gate_fail", 0)

            return {
                "period_minutes": since_minutes,
                "total_events": total,
                "by_event": by_event,
                "by_node": by_node,
                "tasks": {
                    "completed": completed,
                    "failed": failed,
                    "success_rate_pct": success_rate,
                },
                "gates": {
                    "passed": gate_pass,
                    "failed": gate_fail,
                },
            }

    def recent_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        """Ultimas tareas con su estado."""
        with self._open_db() as conn:
            rows = conn.execute(
                "SELECT task_id, "
                "  MAX(CASE WHEN event='task_completed' THEN ts END) as completed_at, "
                "  MAX(CASE WHEN event='task_failed' THEN ts END) as failed_at, "
                "  MAX(CASE WHEN event='task_started' THEN ts END) as started_at, "
                "  MAX(CASE WHEN event='gate_pass' THEN ts END) as gate_at "
                "FROM metrics "
                "WHERE task_id != '' "
                "GROUP BY task_id "
                "ORDER BY MAX(ts) DESC LIMIT ?",
                (limit,),
            ).fetchall()

        result = []
        for r in rows:
            status = "done" if r[1] else ("failed" if r[2] else ("in_progress" if r[3] else "pending"))
            result.append(
                {
                    "task_id": r[0],
                    "status": status,
                    "completed_at": r[1],
                    "failed_at": r[2],
                    "started_at": r[3],
                    "gate_at": r[4],
                }
            )
        return result

    def clear_old(self, days: int = 30) -> int:
        """Limpia metricas antiguas. Retorna count eliminado."""
        with self._lock, self._open_db() as conn:
            cursor = conn.execute(
                "DELETE FROM metrics WHERE ts < datetime('now', ? || ' days')",
                (f"-{days}",),
            )
            count = cursor.rowcount
        if count > 0:
            log.info("[TELEMETRY] Cleaned %d old metrics (> %d days)", count, days)
        return int(count)


def dashboard_html(stats: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    """Genera HTML del dashboard de telemetria (XSS-safe via html.escape)."""
    import html

    event_rows = ""
    for event, count in stats.get("by_event", {}).items():
        event_rows += f"<tr><td>{html.escape(str(event))}</td><td>{count}</td></tr>\n"

    task_rows = ""
    for t in tasks:
        color = {"done": "#2ea043", "failed": "#da3633", "in_progress": "#d29922"}.get(t["status"], "#8b949e")
        task_rows += (
            f"<tr><td><code>{html.escape(t['task_id'])}</code></td>"
            f'<td style="color:{color};font-weight:bold">{html.escape(t["status"])}</td>'
            f"<td>{html.escape(str(t.get('started_at', '-') or '-'))}</td>"
            f"<td>{html.escape(str(t.get('completed_at', '-') or '-'))}</td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>URA Orchestrator Dashboard</title>
<style>
  body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #0d1117; color: #c9d1d9; }}
  h1 {{ color: #58a6ff; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; min-width: 150px; }}
  .card h3 {{ margin: 0; color: #8b949e; font-size: 12px; text-transform: uppercase; }}
  .card .value {{ font-size: 28px; font-weight: bold; color: #58a6ff; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th, td {{ padding: 8px 12px; border: 1px solid #30363d; text-align: left; }}
  th {{ background: #161b22; color: #8b949e; }}
  code {{ background: #1f2937; padding: 2px 6px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>URA Orchestrator Dashboard</h1>
<p>Last {stats.get("period_minutes", 60)} minutes | {stats.get("total_events", 0)} total events</p>

<div class="cards">
  <div class="card"><h3>Tasks Completed</h3><div class="value">{stats["tasks"]["completed"]}</div></div>
  <div class="card"><h3>Tasks Failed</h3><div class="value" style="color:#da3633">{stats["tasks"]["failed"]}</div></div>
  <div class="card"><h3>Success Rate</h3><div class="value">{stats["tasks"]["success_rate_pct"]}%</div></div>
  <div class="card"><h3>Gates Passed</h3><div class="value" style="color:#2ea043">{stats["gates"]["passed"]}</div></div>
  <div class="card"><h3>Gates Failed</h3><div class="value" style="color:#da3633">{stats["gates"]["failed"]}</div></div>
</div>

<h2>Events by Type</h2>
<table><tr><th>Event</th><th>Count</th></tr>{event_rows}</table>

<h2>Recent Tasks</h2>
<table><tr><th>Task ID</th><th>Status</th><th>Started</th><th>Completed</th></tr>{task_rows}</table>

<p style="color:#8b949e;margin-top:40px">Auto-refresh: 30s | Node: {stats.get("by_node", {})}</p>
</body></html>"""
