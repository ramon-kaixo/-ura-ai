"""UserPreferenceLearning — aprende preferencias del usuario con el tiempo (D3).

Observa el comportamiento del usuario y adapta:
  - Longitud preferida (corto/normal/largo)
  - Formato preferido (texto/bullets/codigo)
  - Modo preferido (conversacion/trabajo/explicacion)
  - Temas frecuentes
  - Horas de uso
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

from motor.assistant.config import config


class UserPreferenceLearning:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or config.db_for("preferences")
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = {}
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
                hour INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                timestamp TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_pref_user ON interactions(user_id)")
        self._conn.commit()

    def record(
        self,
        user_id: str,
        intent: str,
        message_length: int = 0,
        mode: str = "conversacion",
        success: bool = True,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO interactions (user_id, intent, message_length, mode, hour, success) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, intent, message_length, mode, time.localtime().tm_hour, int(success)),
            )
            self._conn.commit()
        self._invalidate_cache(user_id)

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        if user_id in self._cache:
            return self._cache[user_id]

        prefs: dict[str, Any] = {
            "preferred_length": "normal",
            "preferred_mode": "conversacion",
            "common_intents": [],
            "active_hours": [],
            "avg_message_length": 50,
        }

        rows = self._conn.execute(
            "SELECT intent, message_length, mode, hour FROM interactions WHERE user_id = ? ORDER BY id DESC LIMIT 100",
            (user_id,),
        ).fetchall()

        if not rows:
            self._cache[user_id] = prefs
            return prefs

        lengths = [r[1] for r in rows]
        modes = [r[2] for r in rows]
        hours = [r[3] for r in rows]
        intents = [r[0] for r in rows]

        avg_length = sum(lengths) / len(lengths)
        if avg_length < 30:
            prefs["preferred_length"] = "short"
        elif avg_length > 150:
            prefs["preferred_length"] = "long"

        if modes:
            prefs["preferred_mode"] = max(set(modes), key=modes.count)

        prefs["common_intents"] = [i for i, _ in Counter(intents).most_common(5)]
        prefs["active_hours"] = sorted(set(hours))
        prefs["avg_message_length"] = int(avg_length)

        self._cache[user_id] = prefs
        return prefs

    def _invalidate_cache(self, user_id: str) -> None:
        self._cache.pop(user_id, None)
