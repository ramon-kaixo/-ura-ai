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
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent.parent / "data" / "task_queue.db"
_STALE_TIMEOUT_S = 300  # 5 min (default si no se especifica timeout_seconds)
_HEARTBEAT_TIMEOUT_S = 60
_DEFAULT_TASK_TIMEOUT_S = 1800  # 30 min


class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    REVIEW = "review"
    DONE = "done"
    FAILED = "failed"
    FAILED_HUMAN = "failed_require_human"
    TIMEOUT = "timeout"


class TaskEvent(StrEnum):
    CREATED = "created"
    ASSIGNED = "assigned"
    STARTED = "started"
    PAUSED = "paused"
    RESUMED = "resumed"
    REVIEWED = "reviewed"
    MERGED = "merged"
    FAILED = "failed"
    RETRY = "retry"
    TIMEOUT = "timeout"
    HUMAN_REVIEW = "human_review"


class TaskStateError(Exception):
    """Lanzada cuando se intenta una transición de estado inválida."""


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
    timeout_seconds INTEGER DEFAULT 1800,
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
    timestamp TEXT NOT NULL,
    automatic INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id);
"""


@contextmanager
def _open_db(db_path: Path) -> Iterator[sqlite3.Connection]:
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


class _PersistentConnection:
    """Long-lived SQLite connection with WAL mode and auto-reconnect."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._connect()

    def _connect(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), timeout=10)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        _migrate_schema(self._conn)

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            conn = self._conn
            assert conn is not None
            try:
                return conn.execute(sql, params)
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                log.warning("[DB] Reconnecting: %s", e)
                self._connect()
                conn = self._conn
                assert conn is not None
                return conn.execute(sql, params)

    def executescript(self, script: str) -> None:
        with self._lock:
            conn = self._conn
            assert conn is not None
            try:
                conn.executescript(script)
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                log.warning("[DB] Reconnecting: %s", e)
                self._connect()
                conn = self._conn
                assert conn is not None
                conn.executescript(script)

    def commit(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.commit()

    def rollback(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.rollback()

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def is_alive(self) -> bool:
        try:
            with self._lock:
                if self._conn:
                    self._conn.execute("SELECT 1")
                    return True
        except Exception as e:
            log.warning("DB is_alive check fallo: %s", e)
        return False


def init_db(db_path: Path | None = None) -> None:
    """Inicializa el schema de la cola de tareas."""
    path = db_path or _DEFAULT_DB
    with _open_db(path) as conn:
        conn.executescript(_SCHEMA)
        # Migration: add node_id if missing
        try:
            conn.execute("SELECT node_id FROM tasks LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE tasks ADD COLUMN node_id TEXT DEFAULT ''")
            log.info("[TASK_QUEUE] Migrated: added node_id column")
        _migrate_schema(conn)
    log.info("[TASK_QUEUE] DB inicializada: %s", path)


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Migraciones idempotentes de esquema (P3 auditoría 2026-08-28).

    - schema_version (v1)
    - tasks_archive (historial de tareas done/failed >30 días)
    - task_events.automatic (trazabilidad de eventos del sistema)
    """
    # 1) schema_version
    if not conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'").fetchone():
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL, applied_at TEXT NOT NULL)")
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (1, ?)",
            (datetime.now(UTC).isoformat(),),
        )
        log.info("[TASK_QUEUE] Migrated: schema_version v1")

    # 2) tasks_archive
    if not conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks_archive'").fetchone():
        conn.execute(
            """
            CREATE TABLE tasks_archive (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                plan_phase TEXT DEFAULT '',
                assigned_to TEXT DEFAULT '',
                status TEXT DEFAULT 'done',
                priority INTEGER DEFAULT 0,
                retries INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                timeout_seconds INTEGER DEFAULT 1800,
                context_json TEXT DEFAULT '{}',
                worktree_path TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT DEFAULT '',
                last_heartbeat TEXT DEFAULT '',
                error_log TEXT DEFAULT '',
                commit_sha TEXT DEFAULT '',
                reviewer TEXT DEFAULT '',
                node_id TEXT DEFAULT '',
                archived_at TEXT NOT NULL
            )
            """
        )
        log.info("[TASK_QUEUE] Migrated: tasks_archive")

    # 3) task_events.automatic
    cols = {r[1] for r in conn.execute("PRAGMA table_info(task_events)")}
    if "automatic" not in cols:
        conn.execute("ALTER TABLE task_events ADD COLUMN automatic INTEGER DEFAULT 0")
        conn.execute(
            "UPDATE task_events SET automatic=1 WHERE event IN ('retry','assigned','started','cleanup','fail_auto')"
        )
        log.info("[TASK_QUEUE] Migrated: task_events.automatic")

    # 4) Archivar tareas done/failed con completed_at o updated_at >30 días
    cutoff = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    rows = conn.execute(
        """
        SELECT id FROM tasks
        WHERE status IN ('done','failed')
          AND (completed_at != '' AND completed_at < ?)
           OR (completed_at = '' AND updated_at != '' AND updated_at < ?)
        """,
        (cutoff, cutoff),
    ).fetchall()
    for (tid,) in rows:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        if not row:
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO tasks_archive
                (id, description, plan_phase, assigned_to, status, priority, retries,
                 max_retries, timeout_seconds, context_json, worktree_path, created_at,
                 updated_at, completed_at, last_heartbeat, error_log, commit_sha,
                 reviewer, node_id, archived_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["id"],
                row["description"],
                row["plan_phase"],
                row["assigned_to"],
                row["status"],
                row["priority"],
                row["retries"],
                row["max_retries"],
                row["timeout_seconds"],
                row["context_json"],
                row["worktree_path"],
                row["created_at"],
                row["updated_at"],
                row["completed_at"],
                row["last_heartbeat"],
                row["error_log"],
                row["commit_sha"],
                row["reviewer"],
                row["node_id"],
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
    if rows:
        log.info("[TASK_QUEUE] Archivadas %d tareas antiguas", len(rows))


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
    timeout_seconds: int = _DEFAULT_TASK_TIMEOUT_S
    context_json: str = "{}"
    worktree_path: str = ""
    created_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    last_heartbeat: str = ""
    error_log: str = ""
    commit_sha: str = ""
    reviewer: str = ""
    node_id: str = ""

    @property
    def heartbeat_interval_s(self) -> int:
        """Heartbeat interval: min(10, timeout_seconds/10)."""
        return min(10, max(1, self.timeout_seconds // 10))

    @property
    def stale_timeout_s(self) -> int:
        """Stale timeout for this task."""
        return self.timeout_seconds

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["heartbeat_interval_s"] = self.heartbeat_interval_s
        return d


# ---------------------------------------------------------------------------
# Queue operations
# ---------------------------------------------------------------------------


class TaskQueue:
    """Cola de tareas SQLite thread-safe."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or _DEFAULT_DB
        init_db(self._db_path)
        self._lock = threading.Lock()
        self._db = _PersistentConnection(self._db_path)
        self._db = _PersistentConnection(self._db_path)

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def create(
        self,
        description: str,
        plan_phase: str = "",
        priority: int = 0,
        max_retries: int = 3,
        timeout_seconds: int = _DEFAULT_TASK_TIMEOUT_S,
        context_json: str = "{}",
        node_id: str = "",
    ) -> Task:
        """Crea una tarea nueva."""
        task_id = f"TASK-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        now = self._now()
        with self._lock, _open_db(self._db_path) as conn:
            conn.execute(
                """INSERT INTO tasks
                   (id, description, plan_phase, priority, max_retries,
                    timeout_seconds, context_json, created_at, updated_at, node_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    description,
                    plan_phase,
                    priority,
                    max_retries,
                    timeout_seconds,
                    context_json,
                    now,
                    now,
                    node_id,
                ),
            )
            conn.execute(
                """INSERT INTO task_events (task_id, event, details, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (task_id, TaskEvent.CREATED.value, description, now),
            )
        log.info("[TASK_QUEUE] Tarea creada: %s", task_id)
        result = self.get(task_id)
        if result is None:
            raise RuntimeError(f"No se pudo recuperar la tarea recién creada {task_id}")
        return result

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
                    """INSERT INTO task_events (task_id, event, agent, timestamp, automatic)
                       VALUES (?, ?, ?, ?, 1)""",
                    (task_id, TaskEvent.ASSIGNED.value, agent, now),
                )
                log.info("[TASK_QUEUE] %s reclamada por %s", task_id, agent)
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if row:
                    return Task(**dict(row))
        return None

    def claim_next(self, agent: str, node_id: str = "") -> Task | None:
        """Reclama la siguiente tarea disponible, priorizando las del propio nodo.

        Cola común con preferencia: primero las tareas cuyo ``node_id`` coincide
        con el del worker; si no hay, toma cualquier tarea ``pending``/``timeout``
        (work-stealing del pool). Devuelve ``None`` si no hay trabajo disponible.
        """
        now = self._now()
        with self._lock, _open_db(self._db_path) as conn:
            if node_id:
                prefs = conn.execute(
                    """SELECT id FROM tasks
                       WHERE status IN ('pending', 'timeout') AND node_id = ?
                       ORDER BY priority DESC, created_at ASC LIMIT 1""",
                    (node_id,),
                ).fetchall()
                if prefs:
                    target = prefs[0]["id"]
                else:
                    row = conn.execute(
                        """SELECT id FROM tasks
                           WHERE status IN ('pending', 'timeout')
                           ORDER BY priority DESC, created_at ASC LIMIT 1""",
                    ).fetchone()
                    target = row["id"] if row else None
            else:
                row = conn.execute(
                    """SELECT id FROM tasks
                       WHERE status IN ('pending', 'timeout')
                       ORDER BY priority DESC, created_at ASC LIMIT 1""",
                ).fetchone()
                target = row["id"] if row else None

            if not target:
                return None

            result = conn.execute(
                """UPDATE tasks
                   SET status = ?, assigned_to = ?, last_heartbeat = ?, updated_at = ?
                   WHERE id = ? AND status IN ('pending', 'timeout')""",
                (TaskStatus.ASSIGNED.value, agent, now, now, target),
            )
            if result.rowcount > 0:
                conn.execute(
                    """INSERT INTO task_events (task_id, event, agent, timestamp, automatic)
                       VALUES (?, ?, ?, ?, 1)""",
                    (target, TaskEvent.ASSIGNED.value, agent, now),
                )
                log.info("[TASK_QUEUE] %s reclamada por %s (node=%s)", target, agent, node_id or "any")
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (target,)).fetchone()
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
                    """INSERT INTO task_events (task_id, event, timestamp, automatic)
                       VALUES (?, ?, ?, 1)""",
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
                    """INSERT INTO task_events (task_id, event, details, timestamp, automatic)
                       VALUES (?, ?, ?, ?, 1)""",
                    (task_id, TaskEvent.MERGED.value, f"commit={commit_sha}", now),
                )
                log.info("[TASK_QUEUE] %s completada (commit: %s)", task_id, commit_sha)
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if row:
                    return Task(**dict(row))
        return None

    def fail(self, task_id: str, error: str, require_human: bool = False) -> Task | None:
        """Marca tarea como fallida. Solo permite fallar tareas ASSIGNED o IN_PROGRESS."""
        now = self._now()
        truncated_error = "\n".join(error.split("\n")[-50:])  # Max 50 líneas

        with self._lock, _open_db(self._db_path) as conn:
            # Read within same lock to prevent race condition
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None

            task = Task(**dict(row))

            # Status guard: only ASSIGNED or IN_PROGRESS can be failed
            if task.status not in (TaskStatus.ASSIGNED.value, TaskStatus.IN_PROGRESS.value):
                raise TaskStateError(
                    f"Cannot fail task {task_id}: status={task.status}, must be 'assigned' or 'in_progress'"
                )

            new_retries = task.retries + 1

            if require_human or new_retries >= task.max_retries:
                status = TaskStatus.FAILED_HUMAN.value
                event = TaskEvent.HUMAN_REVIEW.value
            else:
                status = TaskStatus.FAILED.value
                event = TaskEvent.RETRY.value

            conn.execute(
                """UPDATE tasks
                   SET status = ?, retries = ?, error_log = ?, updated_at = ?
                   WHERE id = ?""",
                (status, new_retries, truncated_error, now, task_id),
            )
            conn.execute(
                """INSERT INTO task_events (task_id, event, details, timestamp, automatic)
                   VALUES (?, ?, ?, ?, 1)""",
                (task_id, event, truncated_error[:500], now),
            )

        log.warning(
            "[TASK_QUEUE] %s falló (retry %d/%d): %s", task_id, new_retries, task.max_retries, truncated_error[:100]
        )
        # Return updated task from same connection
        with _open_db(self._db_path) as conn:
            updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if updated:
                return Task(**dict(updated))
        return None

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
            return bool(result.rowcount > 0)

    def pause(self, task_id: str, node_id: str = "") -> Task | None:
        """Pausa una tarea en progreso (in_progress → paused).

        Queda reservada al nodo que la tenía (worksteal pausado): solo
        ``resume`` de ese nodo la retoma, no se reparte a otros.
        """
        now = self._now()
        with self._lock, _open_db(self._db_path) as conn:
            result = conn.execute(
                """UPDATE tasks
                   SET status = ?, last_heartbeat = ?, updated_at = ?
                   WHERE id = ? AND status IN ('assigned', 'in_progress')""",
                (TaskStatus.PAUSED.value, now, now, task_id),
            )
            if result.rowcount > 0:
                conn.execute(
                    """INSERT INTO task_events (task_id, event, details, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    (task_id, TaskEvent.PAUSED.value, f"node={node_id or ''}", now),
                )
                log.info("[TASK_QUEUE] %s pausada (node=%s)", task_id, node_id or "?")
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if row:
                    return Task(**dict(row))
        return None

    def resume(self, task_id: str, node_id: str = "") -> Task | None:
        """Reanuda una tarea pausada (paused → assigned) para el nodo indicado."""
        now = self._now()
        assign_to = node_id
        if not assign_to:
            existing = self.get(task_id)
            if existing:
                assign_to = existing.assigned_to
        with self._lock, _open_db(self._db_path) as conn:
            result = conn.execute(
                """UPDATE tasks
                   SET status = ?, assigned_to = ?, last_heartbeat = ?, updated_at = ?
                   WHERE id = ? AND status = 'paused'""",
                (TaskStatus.ASSIGNED.value, assign_to, now, now, task_id),
            )
            if result.rowcount > 0:
                conn.execute(
                    """INSERT INTO task_events (task_id, event, details, timestamp, automatic)
                       VALUES (?, ?, ?, ?, 1)""",
                    (task_id, TaskEvent.RESUMED.value, f"node={node_id or ''}", now),
                )
                log.info("[TASK_QUEUE] %s reanudada (node=%s)", task_id, node_id or "?")
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if row:
                    return Task(**dict(row))
        return None

    def list_resumable(self, node_id: str, limit: int = 20) -> list[Task]:
        """Lista tareas pausadas reservadas al nodo dado."""
        with _open_db(self._db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM tasks
                   WHERE status = 'paused' AND assigned_to = ?
                   ORDER BY priority DESC, created_at ASC LIMIT ?""",
                (node_id, limit),
            ).fetchall()
            return [Task(**dict(r)) for r in rows]

    def release_pending(self, node_id: str) -> int:
        """Libera a la cola común las tareas 'assigned'/'in_progress' de un nodo offline.

        Devuelve cuántas tareas se liberaron a``pending`` (work-steal: otro nodo
        puede cogerlas). Las tareas que estaban ``paused`` NO se tocan (Opción C:
        quedan reservadas al nodo que las pausó).
        """
        now = self._now()
        released = 0
        with self._lock, _open_db(self._db_path) as conn:
            rows = conn.execute(
                """SELECT id FROM tasks
                   WHERE status IN ('assigned','in_progress') AND assigned_to = ?""",
                (node_id,),
            ).fetchall()
            for row in rows:
                tid = row["id"]
                conn.execute(
                    """UPDATE tasks
                       SET status = 'pending', assigned_to = '', last_heartbeat = '', updated_at = ?
                       WHERE id = ?""",
                    (now, tid),
                )
                conn.execute(
                    """INSERT INTO task_events (task_id, event, details, timestamp, automatic)
                       VALUES (?, ?, ?, ?, 1)""",
                    (tid, TaskEvent.TIMEOUT.value, f"node offline, released: {node_id}", now),
                )
                released += 1
        if released:
            log.warning("[TASK_QUEUE] %d tareas de %s liberadas a la cola común", released, node_id)
        return released

    def park_in_progress(self, node_id: str) -> int:
        """Convierte en 'paused' las tareas in_progress de un nodo que se detiene.

        Opción C: el trabajo a medias se reserva al nodo; no lo roban los demás.
        Devuelve cuántas tareas se pausaron.
        """
        now = self._now()
        parked = 0
        with self._lock, _open_db(self._db_path) as conn:
            rows = conn.execute(
                """SELECT id FROM tasks
                   WHERE status IN ('assigned','in_progress') AND assigned_to = ?""",
                (node_id,),
            ).fetchall()
            for row in rows:
                tid = row["id"]
                conn.execute(
                    """UPDATE tasks SET status = 'paused', updated_at = ? WHERE id = ?""",
                    (now, tid),
                )
                conn.execute(
                    """INSERT INTO task_events (task_id, event, details, timestamp, automatic)
                       VALUES (?, ?, ?, ?, 1)""",
                    (tid, TaskEvent.PAUSED.value, f"node parked: {node_id}", now),
                )
                parked += 1
        if parked:
            log.warning("[TASK_QUEUE] %d tareas de %s pausadas (reservadas)", parked, node_id)
        return parked

    def steal_available(self, node_id: str, limit: int = 5) -> list[Task]:
        """Robo de trabajo (work-stealing): tareas pending reclamables por este nodo.

        Solo tareas ``pending``/``timeout`` de cola común (no toca ``paused``,
        que están reservadas). Con ``limit=0`` devuelve el conteo.
        """
        with self._lock, _open_db(self._db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM tasks
                   WHERE status IN ('pending','timeout')
                   ORDER BY priority DESC, created_at ASC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [Task(**dict(r)) for r in rows]

    def release_all_paused(self, node_id: str) -> int:
        """Libera a la cola común todas las tareas pausadas de un nodo.

        Opción C + force: para un rebalanceo explícito, las tareas ``paused``
        que quedaron reservadas a un nodo se vuelven ``pending`` para que otro
        nodo del pool las absorba. Devuelve cuántas se liberaron.
        """
        now = self._now()
        released = 0
        with self._lock, _open_db(self._db_path) as conn:
            rows = conn.execute(
                """SELECT id FROM tasks
                   WHERE status = 'paused' AND assigned_to = ?""",
                (node_id,),
            ).fetchall()
            for row in rows:
                tid = row["id"]
                conn.execute(
                    """UPDATE tasks
                       SET status = 'pending', assigned_to = '', last_heartbeat = '', updated_at = ?
                       WHERE id = ?""",
                    (now, tid),
                )
                conn.execute(
                    """INSERT INTO task_events (task_id, event, details, timestamp, automatic)
                       VALUES (?, ?, ?, ?, 1)""",
                    (tid, TaskEvent.TIMEOUT.value, f"paused released (force): {node_id}", now),
                )
                released += 1
        if released:
            log.warning("[TASK_QUEUE] %d tareas pausadas de %s liberadas (force)", released, node_id)
        return released

    def recover_stale(self) -> list[Task]:
        """Recupera tareas stale (sin heartbeat por >timeout_seconds de la tarea)."""
        now_ts = time.time()
        stale = []
        with self._lock, _open_db(self._db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM tasks
                   WHERE status IN ('assigned', 'in_progress')
                   AND last_heartbeat != ''""",
            ).fetchall()
            for row in rows:
                task = Task(**dict(row))
                # Use per-task timeout_seconds
                cutoff_ts = now_ts - task.stale_timeout_s
                cutoff_iso = datetime.fromtimestamp(cutoff_ts, tz=UTC).isoformat()
                if task.last_heartbeat < cutoff_iso:
                    conn.execute(
                        """UPDATE tasks SET status = 'pending', assigned_to = '', updated_at = ?
                           WHERE id = ?""",
                        (self._now(), task.id),
                    )
                    conn.execute(
                        """INSERT INTO task_events (task_id, event, details, timestamp, automatic)
                           VALUES (?, ?, ?, ?, 1)""",
                        (
                            task.id,
                            TaskEvent.TIMEOUT.value,
                            f"heartbeat timeout (limit={task.stale_timeout_s}s)",
                            self._now(),
                        ),
                    )
                    stale.append(task)
        if stale:
            log.warning("[TASK_QUEUE] %d tareas stale recuperadas", len(stale))
        return stale

    def get_events(self, task_id: str) -> list[dict[str, object]]:
        """Obtiene eventos de una tarea."""
        with _open_db(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM task_events WHERE task_id = ? ORDER BY timestamp ASC",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_by_node(self, node_id: str, status: str | None = None, limit: int = 50) -> list[Task]:
        """Lista tareas filtradas por nodo."""
        with _open_db(self._db_path) as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE node_id = ? AND status = ? ORDER BY priority DESC, created_at ASC LIMIT ?",
                    (node_id, status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE node_id = ? ORDER BY priority DESC, created_at ASC LIMIT ?",
                    (node_id, limit),
                ).fetchall()
            return [Task(**dict(r)) for r in rows]

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
