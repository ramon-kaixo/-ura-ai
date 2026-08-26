"""Task Queue — Cola SQLite multi-nodo con API REST.

Schema compatible con el patrón de knowledge/engine/jobs.py:
  - WAL mode para concurrencia
  - Stale recovery automático
  - Heartbeat timeout por nodo
  - Context serialization para context bridge

API REST (FastAPI) en puerto 4097.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent.parent / "data" / "task_queue.db"
_STALE_TIMEOUT_S = 300  # 5 min
_HEARTBEAT_TIMEOUT_S = 60


class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    FAILED = "failed"
    FAILED_HUMAN = "failed_require_human"
    TIMEOUT = "timeout"


class TaskEvent(StrEnum):
    CREATED = "created"
    ASSIGNED = "assigned"
    STARTED = "started"
    REVIEWED = "reviewed"
    MERGED = "merged"
    FAILED = "failed"
    RETRY = "retry"
    TIMEOUT = "timeout"
    HUMAN_REVIEW = "human_review"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    plan_phase TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    retries INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    context_json TEXT DEFAULT '{}',
    worktree_path TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT DEFAULT '',
    last_heartbeat TEXT DEFAULT '',
    error_log TEXT DEFAULT '',
    commit_sha TEXT DEFAULT '',
    reviewer TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT REFERENCES tasks(id),
    event TEXT NOT NULL,
    agent TEXT DEFAULT '',
    details TEXT DEFAULT '',
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id);
"""


@contextmanager
def _open_db(db_path: Path):
    """Abre SQLite con WAL mode y busy timeout (patrón knowledge/engine)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    """Inicializa el schema de la cola de tareas."""
    path = db_path or _DEFAULT_DB
    with _open_db(path) as conn:
        conn.executescript(_SCHEMA)
    log.info("[TASK_QUEUE] DB inicializada: %s", path)


# ---------------------------------------------------------------------------
# Task dataclass
# ---------------------------------------------------------------------------


@dataclass
class Task:
    id: str
    description: str
    plan_phase: str = ""
    assigned_to: str = ""
    status: str = "pending"
    priority: int = 0
    retries: int = 0
    max_retries: int = 3
    context_json: str = "{}"
    worktree_path: str = ""
    created_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    last_heartbeat: str = ""
    error_log: str = ""
    commit_sha: str = ""
    reviewer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Queue operations
# ---------------------------------------------------------------------------


class TaskQueue:
    """Cola de tareas SQLite thread-safe."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or _DEFAULT_DB
        init_db(self._db_path)
        self._lock = threading.Lock()

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def create(
        self,
        description: str,
        plan_phase: str = "",
        priority: int = 0,
        max_retries: int = 3,
        context_json: str = "{}",
    ) -> Task:
        """Crea una tarea nueva."""
        task_id = f"TASK-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        now = self._now()
        with self._lock, _open_db(self._db_path) as conn:
            conn.execute(
                """INSERT INTO tasks
                   (id, description, plan_phase, priority, max_retries,
                    context_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, description, plan_phase, priority, max_retries, context_json, now, now),
            )
            conn.execute(
                """INSERT INTO task_events (task_id, event, details, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (task_id, TaskEvent.CREATED.value, description, now),
            )
        log.info("[TASK_QUEUE] Tarea creada: %s", task_id)
        return self.get(task_id)

    def get(self, task_id: str) -> Task | None:
        """Obtiene una tarea por ID."""
        with _open_db(self._db_path) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                return Task(**dict(row))
        return None

    def list_by_status(self, status: str | None = None, limit: int = 50) -> list[Task]:
        """Lista tareas por estado."""
        with _open_db(self._db_path) as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY priority DESC, created_at ASC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY priority DESC, created_at ASC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [Task(**dict(r)) for r in rows]

    def claim(self, task_id: str, agent: str) -> Task | None:
        """Reclama una tarea (pending → assigned)."""
        now = self._now()
        with self._lock, _open_db(self._db_path) as conn:
            result = conn.execute(
                """UPDATE tasks
                   SET status = ?, assigned_to = ?, last_heartbeat = ?, updated_at = ?
                   WHERE id = ? AND status IN ('pending', 'timeout')""",
                (TaskStatus.ASSIGNED.value, agent, now, now, task_id),
            )
            if result.rowcount > 0:
                conn.execute(
                    """INSERT INTO task_events (task_id, event, agent, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    (task_id, TaskEvent.ASSIGNED.value, agent, now),
                )
                log.info("[TASK_QUEUE] %s reclamada por %s", task_id, agent)
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if row:
                    return Task(**dict(row))
        return None

    def start(self, task_id: str) -> Task | None:
        """Marca tarea como en progreso (assigned → in_progress)."""
        now = self._now()
        with self._lock, _open_db(self._db_path) as conn:
            result = conn.execute(
                """UPDATE tasks
                   SET status = ?, last_heartbeat = ?, updated_at = ?
                   WHERE id = ? AND status = 'assigned'""",
                (TaskStatus.IN_PROGRESS.value, now, now, task_id),
            )
            if result.rowcount > 0:
                conn.execute(
                    """INSERT INTO task_events (task_id, event, timestamp)
                       VALUES (?, ?, ?)""",
                    (task_id, TaskEvent.STARTED.value, now),
                )
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if row:
                    return Task(**dict(row))
        return None

    def complete(self, task_id: str, commit_sha: str = "") -> Task | None:
        """Marca tarea como completada."""
        now = self._now()
        with self._lock, _open_db(self._db_path) as conn:
            result = conn.execute(
                """UPDATE tasks
                   SET status = ?, commit_sha = ?, completed_at = ?, updated_at = ?
                   WHERE id = ? AND status IN ('in_progress', 'review')""",
                (TaskStatus.DONE.value, commit_sha, now, now, task_id),
            )
            if result.rowcount > 0:
                conn.execute(
                    """INSERT INTO task_events (task_id, event, details, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    (task_id, TaskEvent.MERGED.value, f"commit={commit_sha}", now),
                )
                log.info("[TASK_QUEUE] %s completada (commit: %s)", task_id, commit_sha)
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if row:
                    return Task(**dict(row))
        return None

    def fail(self, task_id: str, error: str, require_human: bool = False) -> Task | None:
        """Marca tarea como fallida."""
        now = self._now()
        task = self.get(task_id)
        if not task:
            return None

        new_retries = task.retries + 1
        truncated_error = "\n".join(error.split("\n")[-50:])  # Max 50 líneas

        if require_human or new_retries >= task.max_retries:
            status = TaskStatus.FAILED_HUMAN.value
            event = TaskEvent.HUMAN_REVIEW.value
        else:
            status = TaskStatus.FAILED.value
            event = TaskEvent.RETRY.value

        with self._lock, _open_db(self._db_path) as conn:
            conn.execute(
                """UPDATE tasks
                   SET status = ?, retries = ?, error_log = ?, updated_at = ?
                   WHERE id = ?""",
                (status, new_retries, truncated_error, now, task_id),
            )
            conn.execute(
                """INSERT INTO task_events (task_id, event, details, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (task_id, event, truncated_error[:500], now),
            )
        log.warning(
            "[TASK_QUEUE] %s falló (retry %d/%d): %s", task_id, new_retries, task.max_retries, truncated_error[:100]
        )
        return self.get(task_id)

    def review(self, task_id: str, reviewer: str) -> Task | None:
        """Marca tarea para revisión."""
        now = self._now()
        with self._lock, _open_db(self._db_path) as conn:
            result = conn.execute(
                """UPDATE tasks
                   SET status = ?, reviewer = ?, updated_at = ?
                   WHERE id = ? AND status = 'in_progress'""",
                (TaskStatus.REVIEW.value, reviewer, now, task_id),
            )
            if result.rowcount > 0:
                conn.execute(
                    """INSERT INTO task_events (task_id, event, agent, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    (task_id, TaskEvent.REVIEWED.value, reviewer, now),
                )
                return self.get(task_id)
        return None

    def heartbeat(self, task_id: str) -> bool:
        """Actualiza heartbeat de una tarea asignada."""
        now = self._now()
        with self._lock, _open_db(self._db_path) as conn:
            result = conn.execute(
                """UPDATE tasks SET last_heartbeat = ? WHERE id = ? AND status IN ('assigned', 'in_progress')""",
                (now, task_id),
            )
            return result.rowcount > 0

    def recover_stale(self) -> list[Task]:
        """Recupera tareas stale (sin heartbeat por >timeout)."""
        cutoff = time.time() - _STALE_TIMEOUT_S
        cutoff_iso = datetime.fromtimestamp(cutoff, tz=UTC).isoformat()
        stale = []
        with self._lock, _open_db(self._db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM tasks
                   WHERE status IN ('assigned', 'in_progress')
                   AND last_heartbeat < ?""",
                (cutoff_iso,),
            ).fetchall()
            for row in rows:
                task = Task(**dict(row))
                conn.execute(
                    """UPDATE tasks SET status = 'pending', assigned_to = '', updated_at = ?
                       WHERE id = ?""",
                    (self._now(), task.id),
                )
                conn.execute(
                    """INSERT INTO task_events (task_id, event, details, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    (task.id, TaskEvent.TIMEOUT.value, "heartbeat timeout", self._now()),
                )
                stale.append(task)
        if stale:
            log.warning("[TASK_QUEUE] %d tareas stale recuperadas", len(stale))
        return stale

    def get_events(self, task_id: str) -> list[dict]:
        """Obtiene eventos de una tarea."""
        with _open_db(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM task_events WHERE task_id = ? ORDER BY timestamp ASC",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        """Estadísticas de la cola."""
        with _open_db(self._db_path) as conn:
            counts = {}
            for status in TaskStatus:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM tasks WHERE status = ?",
                    (status.value,),
                ).fetchone()
                counts[status.value] = row["cnt"]
            total = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()["cnt"]
            return {"total": total, "by_status": counts}
