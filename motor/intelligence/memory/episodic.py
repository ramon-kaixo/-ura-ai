"""EpisodeStore — almacén de memoria episódica con persistencia opcional en SQLite."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from motor.intelligence.memory.record import MemoryRecord, MemoryType

log = logging.getLogger("ura.memory.episodic")

ONE_DAY = 86400
ONE_WEEK = 7 * ONE_DAY


@dataclass
class EpisodeStoreConfig:
    max_episodes: int = 10000
    default_ttl: int = ONE_WEEK
    persist_path: str | None = None


@dataclass
class Episode:
    id: str = ""
    session_id: str = ""
    timestamp: str = ""
    source: str = ""
    payload: str = ""
    importance: float = 0.5
    confidence: float = 0.5
    tags: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    ttl: int = ONE_WEEK
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:16]
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()
        if self.ttl <= 0:
            self.ttl = ONE_WEEK

    def to_record(self) -> MemoryRecord:
        return MemoryRecord(
            id=self.id,
            type=MemoryType.EPISODIC,
            timestamp=self.timestamp,
            source=self.source,
            importance=self.importance,
            confidence=self.confidence,
            tags=list(self.tags),
            references=list(self.references),
            ttl=self.ttl,
            metadata={**self.metadata, "session_id": self.session_id},
            payload=self.payload,
        )

    @classmethod
    def from_record(cls, record: MemoryRecord, session_id: str = "") -> Episode:
        return cls(
            id=record.id,
            session_id=session_id or record.metadata.get("session_id", ""),
            timestamp=record.timestamp,
            source=record.source,
            payload=record.payload,
            importance=record.importance,
            confidence=record.confidence,
            tags=list(record.tags),
            references=list(record.references),
            ttl=record.ttl or ONE_WEEK,
            metadata=dict(record.metadata),
        )

    @property
    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        created = datetime.fromisoformat(self.timestamp)
        age = (datetime.now(UTC) - created).total_seconds()
        return age > self.ttl

    @property
    def age_seconds(self) -> float:
        created = datetime.fromisoformat(self.timestamp)
        return (datetime.now(UTC) - created).total_seconds()


class EpisodeStore:
    def __init__(self, config: EpisodeStoreConfig | None = None) -> None:
        self._config = config or EpisodeStoreConfig()
        self._episodes: dict[str, Episode] = {}
        self._by_session: dict[str, set[str]] = {}
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        path = self._config.persist_path
        if not path:
            return
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(str(p), check_same_thread=False)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    timestamp TEXT,
                    source TEXT,
                    payload TEXT,
                    importance REAL,
                    confidence REAL,
                    tags TEXT,
                    refs TEXT,
                    ttl INTEGER,
                    metadata TEXT
                )
            """)
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_session ON episodes(session_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_ts ON episodes(timestamp)")
            self._conn.commit()
            self._load_from_db()
        except sqlite3.DatabaseError:
            log.warning("EpisodeStore DB corrupt at %s, recreating", p)
            p.unlink(missing_ok=True)
            self._conn = sqlite3.connect(str(p), check_same_thread=False)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    timestamp TEXT,
                    source TEXT,
                    payload TEXT,
                    importance REAL,
                    confidence REAL,
                    tags TEXT,
                    refs TEXT,
                    ttl INTEGER,
                    metadata TEXT
                )
            """)
            self._conn.commit()

    def _load_from_db(self) -> None:
        if self._conn is None:
            return
        rows = self._conn.execute("SELECT * FROM episodes").fetchall()
        cols = [d[1] for d in self._conn.execute("PRAGMA table_info(episodes)").fetchall()]
        for row in rows:
            d = dict(zip(cols, row, strict=False))
            try:
                ep = Episode(
                    id=d["id"],
                    session_id=d["session_id"],
                    timestamp=d["timestamp"],
                    source=d.get("source", ""),
                    payload=d.get("payload", ""),
                    importance=float(d.get("importance", 0.5)),
                    confidence=float(d.get("confidence", 0.5)),
                    tags=json.loads(d.get("tags", "[]")),
                    references=json.loads(d.get("refs", "[]")),
                    ttl=int(d.get("ttl", ONE_WEEK)),
                    metadata=json.loads(d.get("metadata", "{}")),
                )
                self._episodes[ep.id] = ep
                self._by_session.setdefault(ep.session_id, set()).add(ep.id)
            except Exception as exc:
                log.warning("Error loading episode %s: %s", d.get("id", "?"), exc)

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def store(self, episode: Episode) -> str:
        with self._lock:
            if not episode.id:
                episode.id = uuid.uuid4().hex[:16]
            if not episode.timestamp:
                episode.timestamp = datetime.now(UTC).isoformat()

            self._episodes[episode.id] = episode
            self._by_session.setdefault(episode.session_id, set()).add(episode.id)
            self._trim()
            self._persist(episode)
            return episode.id

    def get(self, episode_id: str) -> Episode | None:
        with self._lock:
            ep = self._episodes.get(episode_id)
            if ep is None:
                return None
            if ep.is_expired:
                self._delete(episode_id)
                return None
            return ep

    def get_by_session(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Episode]:
        with self._lock:
            ids = list(self._by_session.get(session_id, set()))
        episodes = [self.get(eid) for eid in ids]
        episodes = [e for e in episodes if e is not None]
        episodes.sort(key=lambda e: e.timestamp, reverse=True)
        return episodes[offset : offset + limit]

    def get_by_time_range(
        self,
        start: str,
        end: str,
        limit: int = 100,
    ) -> list[Episode]:
        with self._lock:
            result = []
            for ep in list(self._episodes.values()):
                if start <= ep.timestamp <= end and not ep.is_expired:
                    result.append(ep)  # noqa: PERF401
            result.sort(key=lambda e: e.timestamp, reverse=True)
            return result[:limit]

    def get_recent(self, k: int = 10) -> list[Episode]:
        with self._lock:
            valid = [e for e in self._episodes.values() if not e.is_expired]
            valid.sort(key=lambda e: e.timestamp, reverse=True)
            return valid[:k]

    def count(self, session_id: str | None = None) -> int:
        with self._lock:
            if session_id:
                return len(self._by_session.get(session_id, set()))
            return len(self._episodes)

    def delete(self, episode_id: str) -> bool:
        with self._lock:
            return self._delete(episode_id)

    def _delete(self, episode_id: str) -> bool:
        ep = self._episodes.pop(episode_id, None)
        if ep is None:
            return False
        self._by_session.get(ep.session_id, set()).discard(episode_id)
        self._persist_delete(episode_id)
        return True

    def delete_expired(self) -> int:
        with self._lock:
            expired = [eid for eid, ep in list(self._episodes.items()) if ep.is_expired]
            for eid in expired:
                self._delete(eid)
            return len(expired)

    def clear_session(self, session_id: str) -> int:
        with self._lock:
            ids = list(self._by_session.get(session_id, set()))
            for eid in ids:
                self._delete(eid)
            return len(ids)

    def clear_all(self) -> int:
        with self._lock:
            count = len(self._episodes)
            self._episodes.clear()
            self._by_session.clear()
            if self._conn:
                self._conn.execute("DELETE FROM episodes")
                self._conn.commit()
            return count

    # ── Mantenimiento ──────────────────────────────────────────────────────────

    def _trim(self) -> None:
        if len(self._episodes) <= self._config.max_episodes:
            return
        sorted_eps = sorted(self._episodes.values(), key=lambda e: e.timestamp)
        to_remove = len(self._episodes) - self._config.max_episodes
        for ep in sorted_eps[:to_remove]:
            self._delete(ep.id)

    # ── Persistencia ───────────────────────────────────────────────────────────

    def _persist(self, episode: Episode) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO episodes
                   (id, session_id, timestamp, source, payload, importance,
                    confidence, tags, refs, ttl, metadata)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    episode.id,
                    episode.session_id,
                    episode.timestamp,
                    episode.source,
                    episode.payload,
                    episode.importance,
                    episode.confidence,
                    json.dumps(episode.tags),
                    json.dumps(episode.references),
                    episode.ttl,
                    json.dumps(episode.metadata),
                ),
            )
            self._conn.commit()
        except Exception as exc:
            log.warning("Error persisting episode %s: %s", episode.id, exc)

    def _persist_delete(self, episode_id: str) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
            self._conn.commit()
        except Exception as exc:
            log.warning("Error deleting episode %s from db: %s", episode_id, exc)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


class SessionMemory:
    def __init__(self, store: EpisodeStore | None = None) -> None:
        self._store = store or EpisodeStore()
        self._active_sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    @property
    def store(self) -> EpisodeStore:
        return self._store

    def create_session(
        self,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        sid = session_id or uuid.uuid4().hex[:12]
        with self._lock:
            self._active_sessions[sid] = {
                "created_at": datetime.now(UTC).isoformat(),
                "episode_count": 0,
                "metadata": metadata or {},
            }
        return sid

    def add_episode(
        self,
        session_id: str,
        payload: str,
        source: str = "",
        importance: float = 0.5,
        confidence: float = 0.5,
        tags: list[str] | None = None,
    ) -> Episode:
        ep = Episode(
            session_id=session_id,
            payload=payload,
            source=source,
            importance=importance,
            confidence=confidence,
            tags=tags or [],
        )
        eid = self._store.store(ep)
        with self._lock:
            if session_id in self._active_sessions:
                self._active_sessions[session_id]["episode_count"] = self._store.count(session_id)
        ep.id = eid
        return ep

    def get_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[Episode]:
        return self._store.get_by_session(session_id, limit=limit)

    def get_recent(self, k: int = 10) -> list[Episode]:
        return self._store.get_recent(k=k)

    def session_count(self) -> int:
        with self._lock:
            return len(self._active_sessions)

    def close_session(self, session_id: str) -> bool:
        with self._lock:
            return self._active_sessions.pop(session_id, None) is not None
