"""SharedDB — única base de datos SQLite para todo el asistente."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class SharedDB:
    """Singleton que unifica las 6 bases de datos en una sola conexión."""

    _instance: SharedDB | None = None
    _lock = threading.Lock()

    def __new__(cls) -> SharedDB:  # noqa: PYI034
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False  # noqa: SLF001
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def connect(self, db_path: str | None = None) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        path = db_path or "/tmp/ura/ura.db"  # noqa: S108
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(p), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_tables()
        return self._conn

    def _init_tables(self) -> None:
        if self._conn is None:
            return
        tables = [
            """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                tool_call_id TEXT DEFAULT '',
                tool_name TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            )""",
            """CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                original_claim TEXT NOT NULL,
                corrected_fact TEXT NOT NULL,
                user_message TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now')),
                confidence REAL DEFAULT 1.0,
                applied_count INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS feedback_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                original_message TEXT DEFAULT '',
                user_message TEXT DEFAULT '',
                assistant_response TEXT DEFAULT '',
                score REAL DEFAULT 0.0,
                timestamp TEXT DEFAULT (datetime('now'))
            )""",
            """CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                intent TEXT NOT NULL,
                message_length INTEGER DEFAULT 0,
                mode TEXT DEFAULT 'conversacion',
                success INTEGER DEFAULT 1,
                timestamp TEXT DEFAULT (datetime('now'))
            )""",
            """CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                conversation_id TEXT DEFAULT '',
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT DEFAULT ''
            )""",
            """CREATE TABLE IF NOT EXISTS conversation_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                token TEXT NOT NULL,
                message_role TEXT NOT NULL,
                message_preview TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now'))
            )""",
        ]
        for sql in tables:
            self._conn.execute(sql)
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_corrections_topic ON corrections(topic)",
            "CREATE INDEX IF NOT EXISTS idx_feedback_conv ON feedback_signals(conversation_id)",
            "CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_tokens_token ON conversation_tokens(token)",
        ]
        for sql in indices:
            self._conn.execute(sql)
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        return self._conn  # type: ignore[return-value]

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self.conn.execute(sql, params)

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
