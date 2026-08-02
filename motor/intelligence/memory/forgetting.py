"""Olvido dirigido — políticas de retención, protección, trazabilidad."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from motor.intelligence.memory.episodic import Episode, EpisodeStore
from motor.intelligence.memory.semantic import SemanticFact, SemanticMemoryStore

log = logging.getLogger("ura.memory.forgetting")
ONE_DAY = 86400


@dataclass
class ForgettingEvent:
    record_id: str
    record_type: str
    reason: str
    policy: str
    timestamp: str
    importance: float
    age_days: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "reason": self.reason,
            "policy": self.policy,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "age_days": round(self.age_days, 1),
        }


@dataclass
class ForgettingResult:
    episodes_removed: int = 0
    facts_removed: int = 0
    summaries_removed: int = 0
    protected_skipped: int = 0
    pinned_skipped: int = 0
    referenced_skipped: int = 0
    total_evaluated: int = 0
    elapsed_ms: float = 0.0
    dry_run: bool = False
    details: list[ForgettingEvent] = field(default_factory=list)

    @property
    def total_removed(self) -> int:
        return self.episodes_removed + self.facts_removed + self.summaries_removed


@dataclass
class ForgettingContext:
    episode_store: EpisodeStore
    semantic_store: SemanticMemoryStore
    summaries: list  # list[SummaryRecord]
    protected_ids: set[str]
    pinned_ids: set[str]


class ProtectionRules:
    def __init__(self) -> None:
        self._protected: set[str] = set()
        self._pinned: set[str] = set()

    def protect(self, record_id: str) -> None:
        self._protected.add(record_id)

    def unprotect(self, record_id: str) -> bool:
        if record_id in self._protected:
            self._protected.discard(record_id)
            return True
        return False

    def pin(self, record_id: str) -> None:
        self._pinned.add(record_id)

    def unpin(self, record_id: str) -> bool:
        if record_id in self._pinned:
            self._pinned.discard(record_id)
            return True
        return False

    def is_protected(self, record_id: str) -> bool:
        return record_id in self._protected

    def is_pinned(self, record_id: str) -> bool:
        return record_id in self._pinned

    def count_protected(self) -> int:
        return len(self._protected)

    def count_pinned(self) -> int:
        return len(self._pinned)


class ForgettingPolicy(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def should_forget(self, record: Any, context: ForgettingContext) -> tuple[bool, str]: ...


class NeverForgetPolicy(ForgettingPolicy):
    def name(self) -> str:
        return "never_forget"

    def should_forget(self, record: Any, context: ForgettingContext) -> tuple[bool, str]:
        return False, "policy_never_forget"


class TTLForgetPolicy(ForgettingPolicy):
    def name(self) -> str:
        return "ttl"

    def should_forget(self, record: Any, context: ForgettingContext) -> tuple[bool, str]:
        if isinstance(record, Episode):
            if record.ttl <= 0:
                return False, "no_ttl"
            return record.is_expired, f"ttl_expired_{record.ttl}s"
        if isinstance(record, SemanticFact):
            return False, "semantic_no_ttl"
        return False, "unknown"


class ImportanceForgetPolicy(ForgettingPolicy):
    def __init__(self, min_importance: float = 0.2, min_age_days: int = 30) -> None:
        self._min_imp = min_importance
        self._min_age = timedelta(days=min_age_days)

    def name(self) -> str:
        return "importance"

    def should_forget(self, record: Any, context: ForgettingContext) -> tuple[bool, str]:
        if isinstance(record, Episode):
            if record.importance >= self._min_imp:
                return False, f"importance_{record.importance}_above_{self._min_imp}"
            age = _age_seconds(record.timestamp)
            if age < self._min_age.total_seconds():
                return False, f"age_{age:.0f}s_below_{self._min_age.total_seconds():.0f}s"
            return True, f"importance_{record.importance}_below_{self._min_imp}"
        if isinstance(record, SemanticFact):
            if record.importance >= self._min_imp:
                return False, f"importance_{record.importance}_above_{self._min_imp}"
            return True, f"importance_{record.importance}_below_{self._min_imp}"
        return False, "unknown"


class ConfidenceForgetPolicy(ForgettingPolicy):
    def __init__(self, min_confidence: float = 0.3) -> None:
        self._min_conf = min_confidence

    def name(self) -> str:
        return "confidence"

    def should_forget(self, record: Any, context: ForgettingContext) -> tuple[bool, str]:
        if isinstance(record, Episode):
            if record.confidence >= self._min_conf:
                return False, f"confidence_{record.confidence}_above_{self._min_conf}"
            return True, f"confidence_{record.confidence}_below_{self._min_conf}"
        if isinstance(record, SemanticFact):
            if record.confidence >= self._min_conf:
                return False, f"confidence_{record.confidence}_above_{self._min_conf}"
            return True, f"confidence_{record.confidence}_below_{self._min_conf}"
        return False, "unknown"


class HybridForgetPolicy(ForgettingPolicy):
    def __init__(
        self,
        ttl_policy: TTLForgetPolicy | None = None,
        importance_policy: ImportanceForgetPolicy | None = None,
        confidence_policy: ConfidenceForgetPolicy | None = None,
        require_all: bool = False,
    ) -> None:
        self._ttl = ttl_policy or TTLForgetPolicy()
