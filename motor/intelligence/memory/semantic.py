"""Memoria semántica — hechos, deduplicación, versionado."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from motor.intelligence.memory.episodic import Episode

if TYPE_CHECKING:
    from motor.intelligence.memory.extractor import FactExtractor

log = logging.getLogger("ura.memory.semantic")


@dataclass
class SemanticFact:
    subject: str
    predicate: str
    object_value: str
    fact_type: str = "relation"
    id: str = ""
    confidence: float = 0.5
    importance: float = 0.5
    created_at: str = ""
    updated_at: str = ""
    source_episode_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:16]
        now = datetime.now(UTC).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @property
    def key(self) -> str:
        return f"{self.subject}|{self.predicate}|{self.object_value}"

    def merge(self, other: SemanticFact) -> None:
        self.confidence = max(self.confidence, other.confidence)
        self.importance = max(self.importance, other.importance)
        self.updated_at = datetime.now(UTC).isoformat()
        self.version += 1
        for eid in other.source_episode_ids:
            if eid not in self.source_episode_ids:
                self.source_episode_ids.append(eid)
        for tag in other.tags:
            if tag not in self.tags:
                self.tags.append(tag)
        self.metadata.update(other.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object_value,
            "fact_type": self.fact_type,
            "confidence": self.confidence,
            "importance": self.importance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "source_episodes": len(self.source_episode_ids),
            "tags": self.tags,
        }


class SemanticMemoryStore:
    def __init__(self, persist_path: str | None = None) -> None:
        self._facts: dict[str, SemanticFact] = {}
        self._by_key: dict[str, str] = {}
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._init_db(persist_path)

    def _init_db(self, path: str | None) -> None:
        if not path:
            return
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(p), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_facts (
                id TEXT PRIMARY KEY,
                subject TEXT, predicate TEXT, obj TEXT,
                fact_type TEXT, confidence REAL, importance REAL,
                created_at TEXT, updated_at TEXT, version INTEGER,
                source_ids TEXT, tags TEXT, metadata TEXT
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sf_subj ON semantic_facts(subject)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sf_pred ON semantic_facts(predicate)")
        self._conn.commit()
        self._load_from_db()

    def _load_from_db(self) -> None:
        if self._conn is None:
            return
        rows = self._conn.execute("SELECT * FROM semantic_facts").fetchall()
        cols = [d[1] for d in self._conn.execute("PRAGMA table_info(semantic_facts)").fetchall()]
        for row in rows:
            d = dict(zip(cols, row, strict=False))
            try:
                fact = SemanticFact(
                    id=d["id"],
                    subject=d["subject"],
                    predicate=d["predicate"],
                    object_value=d["obj"],
                    fact_type=d.get("fact_type", "relation"),
                    confidence=float(d.get("confidence", 0.5)),
                    importance=float(d.get("importance", 0.5)),
                    created_at=d.get("created_at", ""),
                    updated_at=d.get("updated_at", ""),
                    version=int(d.get("version", 1)),
                    source_episode_ids=json.loads(d.get("source_ids", "[]")),
                    tags=json.loads(d.get("tags", "[]")),
                    metadata=json.loads(d.get("metadata", "{}")),
                )
                self._facts[fact.id] = fact
                self._by_key[fact.key] = fact.id
            except Exception as exc:
                log.warning("Error loading fact %s: %s", d.get("id", "?"), exc)

    def store(self, fact: SemanticFact) -> str:
        with self._lock:
            existing_id = self._by_key.get(fact.key)
            if existing_id:
                existing = self._facts[existing_id]
                existing.merge(fact)
                self._persist(existing)
                return existing.id
            self._facts[fact.id] = fact
            self._by_key[fact.key] = fact.id
            self._persist(fact)
            return fact.id

    def get(self, fact_id: str) -> SemanticFact | None:
        with self._lock:
            return self._facts.get(fact_id)

    def get_by_key(self, subject: str, predicate: str, object_value: str) -> SemanticFact | None:
        key = f"{subject}|{predicate}|{object_value}"
        with self._lock:
            fid = self._by_key.get(key)
            return self._facts.get(fid) if fid else None

    def search(
        self,
        text: str = "",
        tags: list[str] | None = None,
        fact_type: str | None = None,
        entity: str | None = None,
        k: int = 10,
    ) -> list[SemanticFact]:
        with self._lock:
            results = list(self._facts.values())

        if text:
            text_lower = text.lower()
            results = [
                f
                for f in results
                if text_lower in f.subject.lower()
                or text_lower in f.predicate.lower()
                or text_lower in f.object_value.lower()
            ]

        if tags:
            tag_set = set(tags)
            results = [f for f in results if tag_set & set(f.tags)]

        if fact_type:
            results = [f for f in results if f.fact_type == fact_type]

        if entity:
            entity_lower = entity.lower()
            results = [
                f for f in results if entity_lower in f.subject.lower() or entity_lower in f.object_value.lower()
            ]

        results.sort(key=lambda f: (f.importance, f.confidence), reverse=True)
        return results[:k]

    def delete(self, fact_id: str) -> bool:
        with self._lock:
            fact = self._facts.pop(fact_id, None)
            if fact is None:
                return False
            self._by_key.pop(fact.key, None)
            self._persist_delete(fact_id)
            return True

    def count(self) -> int:
        with self._lock:
            return len(self._facts)

    def clear_all(self) -> int:
        with self._lock:
            n = len(self._facts)
            self._facts.clear()
            self._by_key.clear()
            if self._conn:
                self._conn.execute("DELETE FROM semantic_facts")
                self._conn.commit()
            return n

    def _persist(self, fact: SemanticFact) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO semantic_facts
                   (id, subject, predicate, obj, fact_type, confidence, importance,
                    created_at, updated_at, version, source_ids, tags, metadata)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    fact.id,
                    fact.subject,
                    fact.predicate,
                    fact.object_value,
                    fact.fact_type,
                    fact.confidence,
                    fact.importance,
                    fact.created_at,
                    fact.updated_at,
                    fact.version,
                    json.dumps(fact.source_episode_ids),
                    json.dumps(fact.tags),
                    json.dumps(fact.metadata),
                ),
            )
            self._conn.commit()
        except Exception as exc:
            log.warning("Error persisting fact %s: %s", fact.id, exc)

    def _persist_delete(self, fact_id: str) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("DELETE FROM semantic_facts WHERE id = ?", (fact_id,))
            self._conn.commit()
        except Exception as exc:
            log.warning("Error deleting fact %s: %s", fact_id, exc)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


def consolidate_episodes(
    episodes: list[Episode],
    store: SemanticMemoryStore,
    extractor: FactExtractor,
) -> int:
    total = 0
    for ep in episodes:
        facts = extractor.extract(ep)
        for fact in facts:
            store.store(fact)
            total += 1
    return total
