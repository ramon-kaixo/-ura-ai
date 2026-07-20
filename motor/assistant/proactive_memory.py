"""ProactiveMemory — seguimiento de tareas y proactividad (F29.6 B2).

El sistema recuerda tareas pendientes, hace seguimiento y sugiere
acciones al usuario sin que este las pida.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from motor.assistant.config import config


class Task:
    def __init__(
        self,
        description: str,
        conversation_id: str = "",
        priority: str = "normal",
        status: str = "pending",
        created_at: str = "",
        task_id: str = "",
    ):
        self.task_id = task_id
        self.description = description
        self.conversation_id = conversation_id
        self.priority = priority
        self.status = status
        self.created_at = created_at or datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "conversation_id": self.conversation_id,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
        }


class ProactiveMemory:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or config.db_for("proactive")
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        p = Path(self._db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(p), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                conversation_id TEXT DEFAULT '',
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT DEFAULT ''
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS context_cues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cue_type TEXT NOT NULL,
                cue_text TEXT NOT NULL,
                suggestion TEXT NOT NULL,
                times_triggered INTEGER DEFAULT 0,
                last_triggered TEXT DEFAULT ''
            )
        """)
        self._conn.commit()

    def add_task(self, description: str, conversation_id: str = "", priority: str = "normal") -> Task:
        import uuid
        task = Task(
            task_id=uuid.uuid4().hex[:12],
            description=description,
            conversation_id=conversation_id,
            priority=priority,
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO tasks "
                "(id, description, conversation_id, priority, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (task.task_id, task.description, task.conversation_id, task.priority, task.status, task.created_at),
            )
            self._conn.commit()
        return task

    def get_pending_tasks(self, conversation_id: str = "") -> list[Task]:
        if conversation_id:
            rows = self._conn.execute(
                "SELECT id, description, conversation_id, priority, status, created_at FROM tasks "
                "WHERE status = 'pending' AND conversation_id = ? ORDER BY created_at DESC",
                (conversation_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, description, conversation_id, priority, status, created_at FROM tasks "
                "WHERE status = 'pending' ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
        return [Task(*row) for row in rows]

    def complete_task(self, task_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
                (datetime.now(UTC).isoformat(), task_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def detect_task_trigger(self, user_message: str) -> str | None:
        triggers = [
            (["recuérdame", "no olvides", "apunta", "anota", "pendiente",
              "tengo que", "necesito que"], "add_task"),
            (["ya lo hice", "completado", "terminado", "listo", "hecho",
              "resuelto"], "complete_task"),
            (["qué tengo", "tareas", "pendientes", "qué falta"], "list_tasks"),
        ]
        msg_lower = user_message.lower()
        for keywords, action in triggers:
            if any(k in msg_lower for k in keywords):
                return action
        return None

    def suggest_proactive(self, conversation_id: str) -> str | None:
        pending = self.get_pending_tasks(conversation_id)
        if pending:
            tasks_str = ", ".join(t.description[:50] for t in pending[:3])
            return f"Tienes tareas pendientes: {tasks_str}. ¿Quieres que las revise?"
        return None
