"""Compresión de memoria — políticas, resúmenes extractivos, planificación."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from motor.intelligence.memory.episodic import Episode, EpisodeStore

log = logging.getLogger("ura.memory.compression")

ONE_DAY = 86400


@dataclass
class SummaryRecord:
    source_episode_ids: list[str]
    summary: str
    confidence: float = 0.0
    importance: float = 0.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:16]
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()


@dataclass
class CompressionResult:
    summaries_created: int = 0
    episodes_compressed: int = 0
    episodes_deleted: int = 0
    elapsed_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


class CompressionPolicy(ABC):
    @abstractmethod
    def should_run(self, store: EpisodeStore) -> bool: ...

    @abstractmethod
    def select_candidates(self, store: EpisodeStore) -> list[Episode]: ...

    @property
    @abstractmethod
    def delete_originals(self) -> bool: ...


class NeverCompress(CompressionPolicy):
    def should_run(self, store: EpisodeStore) -> bool:
        return False

    def select_candidates(self, store: EpisodeStore) -> list[Episode]:
        return []

    @property
    def delete_originals(self) -> bool:
        return False


class AgeBasedCompression(CompressionPolicy):
    def __init__(self, max_age_days: int = 7, delete_after_compress: bool = False) -> None:
        self._max_age = timedelta(days=max_age_days)
        self._delete = delete_after_compress

    def should_run(self, store: EpisodeStore) -> bool:
        return True

    def select_candidates(self, store: EpisodeStore) -> list[Episode]:
        cutoff = datetime.now(UTC) - self._max_age
        return [ep for ep in store.get_recent(k=10000) if datetime.fromisoformat(ep.timestamp) < cutoff]

    @property
    def delete_originals(self) -> bool:
        return self._delete


class SizeBasedCompression(CompressionPolicy):
    def __init__(self, max_episodes: int = 5000, delete_after_compress: bool = False) -> None:
        self._max = max_episodes
        self._delete = delete_after_compress

    def should_run(self, store: EpisodeStore) -> bool:
        return store.count() > self._max

    def select_candidates(self, store: EpisodeStore) -> list[Episode]:
        episodes = store.get_recent(k=10000)
        if len(episodes) <= self._max:
            return []
        excess = len(episodes) - self._max
        episodes.sort(key=lambda e: e.timestamp)
        return episodes[:excess]

    @property
    def delete_originals(self) -> bool:
        return self._delete


class HybridCompressionPolicy(CompressionPolicy):
    def __init__(
        self,
        max_age_days: int = 7,
        max_episodes: int = 5000,
        delete_after_compress: bool = False,
    ) -> None:
        self._age_policy = AgeBasedCompression(max_age_days, delete_after_compress)
        self._size_policy = SizeBasedCompression(max_episodes, delete_after_compress)
        self._delete = delete_after_compress

    def should_run(self, store: EpisodeStore) -> bool:
        return self._age_policy.should_run(store) or self._size_policy.should_run(store)

    def select_candidates(self, store: EpisodeStore) -> list[Episode]:
        age_candidates = self._age_policy.select_candidates(store)
        size_candidates = self._size_policy.select_candidates(store)
        seen: set[str] = set()
        merged: list[Episode] = []
        for ep in age_candidates + size_candidates:
            if ep.id not in seen:
                seen.add(ep.id)
                merged.append(ep)
        merged.sort(key=lambda e: e.timestamp)
        return merged

    @property
    def delete_originals(self) -> bool:
        return self._delete


class MemoryCompressor:
    def __init__(
        self,
        store: EpisodeStore,
        policy: CompressionPolicy | None = None,
    ) -> None:
        self._store = store
        self._policy = policy or SizeBasedCompression()
        self._summaries: dict[str, SummaryRecord] = {}
        self._lock = threading.RLock()

    @property
    def policy(self) -> CompressionPolicy:
        return self._policy

    @policy.setter
    def policy(self, new_policy: CompressionPolicy) -> None:
        self._policy = new_policy

    def compress(self) -> CompressionResult:
        start = time.monotonic()
        result = CompressionResult()

        if not self._policy.should_run(self._store):
            result.elapsed_ms = (time.monotonic() - start) * 1000
            return result

        candidates = self._policy.select_candidates(self._store)
        if not candidates:
            result.elapsed_ms = (time.monotonic() - start) * 1000
            return result

        with self._lock:
            groups = self._group_by_session(candidates)

            for session_id, group in groups.items():
                try:
                    summary = self._generate_summary(session_id, group)
                    if summary:
                        self._summaries[summary.id] = summary
                        result.summaries_created += 1
                        result.episodes_compressed += len(group)

                        if self._policy.delete_originals:
                            for ep in group:
                                self._store.delete(ep.id)
                                result.episodes_deleted += 1
                except Exception as exc:
                    result.errors.append(f"Session {session_id}: {exc}")
                    log.warning("Compression error for session %s: %s", session_id, exc)

        result.elapsed_ms = (time.monotonic() - start) * 1000
        return result

    def _group_by_session(self, episodes: list[Episode]) -> dict[str, list[Episode]]:
        groups: dict[str, list[Episode]] = {}
        for ep in episodes:
            sid = ep.session_id or "_no_session"
            groups.setdefault(sid, []).append(ep)
        return groups

    def _generate_summary(self, session_id: str, episodes: list[Episode]) -> SummaryRecord | None:
        if not episodes:
            return None

        episodes.sort(key=lambda e: e.timestamp)
        source_ids = [ep.id for ep in episodes]
        lines: list[str] = []
        total_conf = 0.0
        total_imp = 0.0
        all_tags: set[str] = set()

        seen_texts: set[str] = set()
        for ep in episodes:
            if ep.payload and ep.payload not in seen_texts:
                lines.append(f"[{ep.timestamp[:10]}] {ep.payload[:200]}")
                seen_texts.add(ep.payload)
            total_conf += ep.confidence
            total_imp += ep.importance
            all_tags.update(ep.tags)

        summary_text = "\n".join(lines)
        if not summary_text:
            return None

        total_payload = sum(len(ep.payload) for ep in episodes if ep.payload)
        return SummaryRecord(
            source_episode_ids=source_ids,
            summary=summary_text,
            confidence=round(total_conf / len(episodes), 4),
            importance=round(total_imp / len(episodes), 4),
            tags=sorted(all_tags),
            metadata={
                "session_id": session_id,
                "episode_count": len(episodes),
                "compression_ratio": min(1.0, len(summary_text) / max(total_payload, 1)),
            },
        )

    def get_summaries(
        self,
        session_id: str | None = None,
        k: int = 10,
    ) -> list[SummaryRecord]:
        with self._lock:
            results = list(self._summaries.values())
        if session_id:
            results = [s for s in results if s.metadata.get("session_id") == session_id]
        results.sort(key=lambda s: s.created_at, reverse=True)
        return results[:k]

    def count_summaries(self) -> int:
        with self._lock:
            return len(self._summaries)

    def get_summary(self, summary_id: str) -> SummaryRecord | None:
        with self._lock:
            return self._summaries.get(summary_id)

    def clear_summaries(self) -> int:
        with self._lock:
            n = len(self._summaries)
            self._summaries.clear()
            return n


class CompressionScheduler:
    def __init__(self, compressor: MemoryCompressor) -> None:
        self._compressor = compressor
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True
        log.info("CompressionScheduler enabled")

    def disable(self) -> None:
        self._enabled = False
        log.info("CompressionScheduler disabled")

    def run_once(self) -> CompressionResult:
        return self._compressor.compress()
