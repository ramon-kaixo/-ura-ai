"""ConversationEvaluator — mide calidad de las conversaciones (F1).

Métricas:
  - Tasa de correcciones (corrective_learning)
  - Tasa de reformulación (implicit_feedback)
  - Sentimiento promedio (sentiment)
  - Tareas completadas (proactive_memory)
  - Tasa de interrupción (interruption)
  - Satisfacción implícita
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class ConversationEvaluator:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or "/tmp/ura/evaluation.db"  # noqa: S108
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        p = Path(self._db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(p), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                user_id TEXT DEFAULT '',
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                details TEXT DEFAULT '{}',
                timestamp TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_conv ON evaluations(conversation_id)")
        self._conn.commit()

    def record_metric(self, conversation_id: str, metric_name: str, metric_value: float, details: dict | None = None, user_id: str = "") -> None:  # noqa: E501
        with self._lock:
            self._conn.execute(
                "INSERT INTO evaluations (conversation_id, user_id, metric_name, metric_value, details) VALUES (?, ?, ?, ?, ?)",  # noqa: E501
                (conversation_id, user_id, metric_name, metric_value, json.dumps(details or {})),
            )
            self._conn.commit()

    def get_conversation_score(self, conversation_id: str) -> float:
        rows = self._conn.execute(
            "SELECT metric_value FROM evaluations WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchall()
        if not rows:
            return 0.0
        return sum(r[0] for r in rows) / len(rows)

    def get_summary(self, limit: int = 100) -> dict[str, Any]:
        rows = self._conn.execute(
            "SELECT metric_name, AVG(metric_value), COUNT(*) FROM evaluations "
            "GROUP BY metric_name ORDER BY COUNT(*) DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return {
            "total_evaluations": sum(r[2] for r in rows),
            "metrics": {r[0]: {"avg": round(r[1], 3), "count": r[2]} for r in rows},
        }
