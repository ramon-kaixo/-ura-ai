"""ConversationalLearning — aprende preferencias del usuario (F29 B8)."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any


class UserPreferences:
    def __init__(self) -> None:
        self.preferred_length: str = "normal"
        self.preferred_format: str = "text"
        self.preferred_mode: str = "conversacion"
        self.previous_intents: list[str] = []
        self.repeated_patterns: list[str] = []
        self.custom: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferred_length": self.preferred_length,
            "preferred_format": self.preferred_format,
            "preferred_mode": self.preferred_mode,
            "previous_intents": self.previous_intents[-20:],
            "custom": self.custom,
        }


class ConversationalLearning:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or "/tmp/ura/learning.db"
        self._lock = threading.Lock()
        self._preferences: dict[str, UserPreferences] = {}
        self._init_db()

    def _init_db(self) -> None:
        p = Path(self._db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(p), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                intent TEXT NOT NULL,
                message_length INTEGER DEFAULT 0,
                mode TEXT DEFAULT 'conversacion',
                success INTEGER DEFAULT 1,
                timestamp TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_user ON interactions(user_id)")
        self._conn.commit()

    def record_interaction(
        self,
        user_id: str,
        intent: str,
        message_length: int = 0,
        mode: str = "conversacion",
        success: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO interactions (user_id, intent, message_length, mode, success) VALUES (?, ?, ?, ?, ?)",
                (user_id, intent, message_length, mode, int(success)),
            )
            self._conn.commit()
        self._update_preferences(user_id)

    def get_preferences(self, user_id: str) -> UserPreferences:
        if user_id not in self._preferences:
            self._preferences[user_id] = UserPreferences()
            self._load_preferences(user_id)
        return self._preferences[user_id]

    def _load_preferences(self, user_id: str) -> None:
        prefs = self._preferences[user_id]
        rows = self._conn.execute(
            "SELECT intent, message_length, mode FROM interactions WHERE user_id = ? ORDER BY id DESC LIMIT 50",
            (user_id,),
        ).fetchall()
        intents = [r[0] for r in rows]
        lengths = [r[1] for r in rows]
        modes = [r[2] for r in rows]

        if lengths:
            avg = sum(lengths) / len(lengths)
            prefs.preferred_length = "short" if avg < 50 else "long" if avg > 200 else "normal"
        if modes:
            prefs.preferred_mode = max(set(modes), key=modes.count)
        prefs.previous_intents = intents

    def _update_preferences(self, user_id: str) -> None:
        if user_id not in self._preferences:
            self._preferences[user_id] = UserPreferences()
        self._load_preferences(user_id)
