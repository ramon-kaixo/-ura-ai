"""VectorMemoryStore — memoria de conversaciones con búsqueda semántica."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

import numpy as np


class VectorMemoryStore:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or "/tmp/ura/vector_memory.db"  # noqa: S108
        self._lock = threading.Lock()
        self._dim = 768
        self._init_db()

    def _init_db(self) -> None:
        p = Path(self._db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(p), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now')),
                embedding BLOB
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_cid ON entries(conversation_id)")
        self._conn.commit()

    def store(self, conversation_id: str, role: str, content: str) -> None:
        if not content or len(content) < 10:
            return
        emb = self._embed(content)
        if emb is None:
            return
        with self._lock:
            self._conn.execute(
                "INSERT INTO entries (conversation_id, role, content, embedding) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content[:500], emb.tobytes()),
            )
            self._conn.commit()

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        qemb = self._embed(query)
        if qemb is None:
            return []
        with self._lock:
            rows = self._conn.execute(
                "SELECT conversation_id, role, content, timestamp, embedding "
                "FROM entries ORDER BY id DESC LIMIT 200"
            ).fetchall()
        if not rows:
            return []
        scored = []
        for row in rows:
            semb = np.frombuffer(row[4], dtype=np.float32)
            sim = self._cosine(qemb, semb)
            if sim > 0.5:
                scored.append((sim, {
                    "conversation_id": row[0], "role": row[1],
                    "content": row[2][:200], "similarity": float(sim),
                }))
        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:limit]]

    def _embed(self, text: str) -> np.ndarray | None:
        try:
            import httpx
            resp = httpx.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text[:512]},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                emb = data.get("embedding")
                if emb:
                    return np.array(emb, dtype=np.float32)
        except Exception:  # noqa: S110
            pass
        return None

    def _cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()
        return row[0] if row else 0
