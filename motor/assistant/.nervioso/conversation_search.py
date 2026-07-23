"""ConversationSearch — búsqueda semántica en conversaciones pasadas."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from motor.assistant.config import config


class ConversationSearch:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or config.db_for("search")
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        p = Path(self._db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(p), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                token TEXT NOT NULL,
                message_role TEXT NOT NULL,
                message_preview TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ct_token ON conversation_tokens(token)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ct_cid ON conversation_tokens(conversation_id)")
        self._conn.commit()

    def index_message(self, conversation_id: str, role: str, content: str) -> None:
        tokens = self._extract_tokens(content)
        preview = content[:100]
        with self._lock:
            for token in set(tokens):
                self._conn.execute(
                    "INSERT INTO conversation_tokens "
                    "(conversation_id, token, message_role, message_preview) "
                    "VALUES (?, ?, ?, ?)",
                    (conversation_id, token, role, preview),
                )
            self._conn.commit()

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        tokens = self._extract_tokens(query)
        if not tokens:
            return []

        if not tokens:
            return []
        sql = (
            "SELECT conversation_id, message_role, message_preview, timestamp, COUNT(*) as match_count "  # nosec
            "FROM conversation_tokens WHERE token IN (" + ",".join("?" for _ in tokens) + ") "
            "GROUP BY conversation_id, message_preview ORDER BY match_count DESC LIMIT ?"
        )
        rows = self._conn.execute(sql, (*tokens, limit)).fetchall()

        return [
            {
                "conversation_id": r[0],
                "role": r[1],
                "preview": r[2],
                "timestamp": r[3],
                "relevance": r[4] / len(tokens),
            }
            for r in rows
        ]

    def _extract_tokens(self, text: str) -> list[str]:
        stop_words = {
            "el",
            "la",
            "los",
            "las",
            "un",
            "una",
            "y",
            "e",
            "o",
            "u",
            "de",
            "del",
            "en",
            "con",
            "por",
            "para",
            "a",
            "ante",
            "bajo",
            "es",
            "son",
            "fue",
            "era",
            "esta",
            "este",
            "que",
            "como",
            "mas",
            "pero",
            "lo",
            "le",
            "se",
            "no",
            "me",
            "te",
        }
        words = text.lower().split()
        return [w for w in words if len(w) > 3 and w not in stop_words]
