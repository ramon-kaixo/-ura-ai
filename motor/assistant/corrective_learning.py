"""CorrectiveLearning — aprende de las correcciones del usuario (F29.6 B1).

Cuando el usuario dice "corrige", "no es correcto", "en realidad" etc.,
el sistema almacena la corrección y la reutiliza en el futuro.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from motor.assistant.config import config


class CorrectiveMemory:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or config.db_for("corrections")
        self._lock = threading.Lock()
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._init_db()

    def _init_db(self) -> None:
        p = Path(self._db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(p), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                original_claim TEXT NOT NULL,
                corrected_fact TEXT NOT NULL,
                user_message TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now')),
                confidence REAL DEFAULT 1.0,
                applied_count INTEGER DEFAULT 0
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_topic ON corrections(topic)")
        self._conn.commit()
        self._load_cache()

    def _load_cache(self) -> None:
        rows = self._conn.execute(
            "SELECT topic, original_claim, corrected_fact, timestamp, confidence "
            "FROM corrections ORDER BY timestamp DESC"
        ).fetchall()
        for row in rows:
            topic = row[0]
            if topic not in self._cache:
                self._cache[topic] = []
            self._cache[topic].append(
                {
                    "original": row[1],
                    "corrected": row[2],
                    "timestamp": row[3],
                    "confidence": row[4],
                }
            )

    def record_correction(
        self,
        user_message: str,
    ) -> dict[str, Any] | None:
        correction = self._parse_correction(user_message)
        if not correction:
            return None

        with self._lock:
            self._conn.execute(
                "INSERT INTO corrections (topic, original_claim, corrected_fact, user_message) VALUES (?, ?, ?, ?)",
                (correction["topic"], correction["original"], correction["corrected"], user_message),
            )
            self._conn.commit()

        if correction["topic"] not in self._cache:
            self._cache[correction["topic"]] = []
        self._cache[correction["topic"]].append(correction)

        return correction

    def get_relevant_corrections(self, user_message: str) -> list[dict[str, Any]]:
        words = user_message.lower().split()
        results: list[dict[str, Any]] = []
        for topic, corrections in self._cache.items():
            if any(word in topic or topic in word for word in words):
                results.extend(corrections)
        return results[-5:]

    def _parse_correction(self, text: str) -> dict[str, Any] | None:
        text_lower = text.lower()

        if "no es" in text_lower:
            parts = text_lower.split("no es", 1)
            if len(parts) == 2 and parts[1].strip():
                topic = self._extract_topic(parts[0])
                return {
                    "topic": topic,
                    "original": parts[0].strip()[-80:],
                    "corrected": parts[1].strip()[:200],
                }

        if "en realidad" in text_lower:
            parts = text_lower.split("en realidad", 1)
            if len(parts) == 2:
                return {
                    "topic": self._extract_topic(text),
                    "original": "afirmación anterior",
                    "corrected": parts[1].strip()[:200],
                }

        if text_lower.startswith("corrige"):
            rest = text[7:].strip()
            if rest:
                return {
                    "topic": self._extract_topic(rest),
                    "original": "información anterior",
                    "corrected": rest[:200],
                }

        return None

    def _extract_topic(self, text: str) -> str:
        words = text.lower().split()
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
            "de",
            "del",
            "en",
            "con",
            "por",
            "para",
            "a",
            "es",
            "que",
            "no",
            "se",
            "su",
            "lo",
            "le",
            "como",
            "más",
        }
        topics = [w for w in words if w not in stop_words and len(w) > 3]
        return topics[0] if topics else text[:30]
