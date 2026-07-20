"""Message store for conversations."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from motor.assistant.config import config
from motor.assistant.models import Message


class MessageStore:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or config.db_for("conversations")
        self._lock = threading.Lock()
        self._closed = False
        self._init_db()

    def _init_db(self) -> None:
        p = Path(self._db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(p), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                tool_call_id TEXT DEFAULT '',
                tool_name TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_conv ON messages(conversation_id, timestamp)")
        self._conn.commit()

    def _check_closed(self) -> None:
        if self._closed:
            raise RuntimeError("MessageStore is closed")

    def append(self, conversation_id: str, message: Message) -> int:
        self._check_closed()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp, tool_call_id, tool_name, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    message.role,
                    message.content,
                    message.timestamp,
                    message.tool_call_id,
                    message.tool_name,
                    json.dumps(message.metadata, skipkeys=True),
                ),
            )
            self._conn.commit()
            return cur.lastrowid or 0

    def get_conversation(self, conversation_id: str, limit: int = 100) -> list[Message]:
        self._check_closed()
        if limit < 1:
            return []
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content, timestamp, tool_call_id, tool_name, metadata "
                "FROM messages WHERE conversation_id = ? ORDER BY id ASC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        return [
            Message(
                role=row[0],
                content=row[1],
                timestamp=row[2],
                tool_call_id=row[3] or "",
                tool_name=row[4] or "",
                metadata=json.loads(row[5]) if row[5] != "{}" else {},
            )
            for row in rows
        ]

    def list_conversations(self) -> list[dict[str, Any]]:
        self._check_closed()
        with self._lock:
            rows = self._conn.execute(
                "SELECT conversation_id, COUNT(*) as msg_count, MIN(timestamp) as created, MAX(timestamp) as updated "
                "FROM messages GROUP BY conversation_id ORDER BY updated DESC"
            ).fetchall()
        return [{"id": r[0], "message_count": r[1], "created_at": r[2], "updated_at": r[3]} for r in rows]

    def delete_conversation(self, conversation_id: str) -> bool:
        self._check_closed()
        with self._lock:
            self._conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            self._conn.commit()
            return self._conn.total_changes > 0

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def __enter__(self) -> MessageStore:  # noqa: PYI034
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
