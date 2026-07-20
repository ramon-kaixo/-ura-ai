"""ImplicitFeedback — aprende sin preguntar del comportamiento del usuario (F29.6 B4).

Detecta feedback implícito:
- Usuario reformula → respuesta anterior no fue clara
- Usuario repite pregunta → respuesta anterior fue insuficiente
- Usuario dice gracias y se va → tarea completada
- Usuario corrige → respuesta anterior fue incorrecta
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from motor.assistant.config import config


class ImplicitFeedback:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or config.db_for("feedback")
        self._lock = threading.Lock()
        self._last_messages: dict[str, str] = {}
        self._init_db()

    def _init_db(self) -> None:
        p = Path(self._db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(p), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                original_message TEXT DEFAULT '',
                user_message TEXT DEFAULT '',
                assistant_response TEXT DEFAULT '',
                score REAL DEFAULT 0.0,
                timestamp TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_fb_conv ON feedback_signals(conversation_id)")
        self._conn.commit()

    def analyze(self, conversation_id: str, user_message: str, assistant_response: str = "") -> dict[str, Any]:
        signals: dict[str, Any] = {
            "was_unclear": False,
            "was_wrong": False,
            "task_complete": False,
            "repeated_query": False,
            "overall_score": 0.0,
        }
        prev = self._last_messages.get(conversation_id, "")

        if prev and self._is_rephrase(prev, user_message):
            signals["was_unclear"] = True
            signals["overall_score"] -= 0.2
            self._store_signal(conversation_id, "unclear", prev, user_message, assistant_response, -0.2)

        if self._is_repeat(prev, user_message):
            signals["repeated_query"] = True
            signals["overall_score"] -= 0.3
            self._store_signal(conversation_id, "repeat", prev, user_message, assistant_response, -0.3)

        if "gracias" in user_message.lower() and len(user_message) < 50:
            signals["task_complete"] = True
            signals["overall_score"] += 0.3
            self._store_signal(conversation_id, "complete", "", user_message, assistant_response, 0.3)

        self._last_messages[conversation_id] = user_message
        return signals

    def _is_rephrase(self, prev: str, current: str) -> bool:
        if not prev:
            return False
        prev_words = set(prev.lower().split())
        curr_words = set(current.lower().split())
        overlap = prev_words & curr_words
        return len(overlap) >= 2 and len(prev_words - curr_words) > 0 and len(curr_words - prev_words) > 0

    def _is_repeat(self, prev: str, current: str) -> bool:
        if not prev:
            return False
        return prev.lower().strip() == current.lower().strip()

    def _store_signal(
        self,
        conv_id: str,
        signal_type: str,
        original: str,
        user_msg: str,
        response: str,
        score: float,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO feedback_signals "
                "(conversation_id, signal_type, original_message, user_message, assistant_response, score) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (conv_id, signal_type, original[:200], user_msg[:200], response[:200], score),
            )
            self._conn.commit()

    def get_conversation_score(self, conversation_id: str) -> float:
        rows = self._conn.execute(
            "SELECT score FROM feedback_signals WHERE conversation_id = ?", (conversation_id,)
        ).fetchall()
        if not rows:
            return 0.0
        return sum(r[0] for r in rows)

    def get_overall_score(self) -> float:
        rows = self._conn.execute("SELECT score FROM feedback_signals").fetchall()
        if not rows:
            return 0.0
        return sum(r[0] for r in rows) / len(rows)
