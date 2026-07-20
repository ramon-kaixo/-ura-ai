"""Olvido dirigido — políticas de retención, protección, trazabilidad."""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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
        self._imp = importance_policy or ImportanceForgetPolicy()
        self._conf = confidence_policy or ConfidenceForgetPolicy()
        self._require_all = require_all

    def name(self) -> str:
        return "hybrid"

    def should_forget(self, record: Any, context: ForgettingContext) -> tuple[bool, str]:
        results: list[tuple[bool, str]] = []
        for p in (self._ttl, self._imp, self._conf):
            decision, reason = p.should_forget(record, context)
            results.append((decision, f"{p.name()}:{reason}"))

        decisions = [d for d, _ in results]
        should = all(decisions) if self._require_all else any(decisions)
        reasons = "; ".join(r for _, r in results)
        return should, reasons


def _age_seconds(timestamp: str) -> float:
    try:
        created = datetime.fromisoformat(timestamp)
        return (datetime.now(UTC) - created).total_seconds()
    except Exception:
        return 0.0


class ForgettingEngine:
    def __init__(
        self,
        episode_store: EpisodeStore,
        semantic_store: SemanticMemoryStore | None = None,
        summaries: list | None = None,
        policies: list[ForgettingPolicy] | None = None,
        protection: ProtectionRules | None = None,
        batch_size: int = 1000,
    ) -> None:
        self._episode_store = episode_store
        self._semantic_store = semantic_store or SemanticMemoryStore()
        self._summaries = summaries or []
        self._policies = policies or [HybridForgetPolicy()]
        self._protection = protection or ProtectionRules()
        self._batch_size = batch_size
        self._lock = threading.RLock()

    def run(self, dry_run: bool = False) -> ForgettingResult:
        start = time.monotonic()
        result = ForgettingResult(dry_run=dry_run)

        protected_ids = set(self._protection._protected)  # noqa: SLF001
        pinned_ids = set(self._protection._pinned)  # noqa: SLF001

        # Collect referenced episode IDs from summaries
        referenced: set[str] = set()
        for s in self._summaries:
            for eid in s.source_episode_ids:
                referenced.add(eid)

        context = ForgettingContext(
            episode_store=self._episode_store,
            semantic_store=self._semantic_store,
            summaries=self._summaries,
            protected_ids=protected_ids,
            pinned_ids=pinned_ids,
        )

        with self._lock:
            result = self._evaluate_episodes(result, context, dry_run)
            result = self._evaluate_facts(result, context, dry_run)
            result.total_evaluated = (
                result.episodes_removed
                + result.facts_removed
                + result.protected_skipped
                + result.pinned_skipped
                + result.referenced_skipped
            )

        result.elapsed_ms = (time.monotonic() - start) * 1000
        return result

    def simulate(self) -> ForgettingResult:
        return self.run(dry_run=True)

    def _evaluate_episodes(self, result: ForgettingResult, ctx: ForgettingContext, dry_run: bool) -> ForgettingResult:
        episodes = list(ctx.episode_store._episodes.values())  # noqa: SLF001  -- incluye expirados para evaluacion
        batch: list[Episode] = []
        for ep in episodes:
            if ep.id in ctx.protected_ids:
                result.protected_skipped += 1
                continue
            if ep.id in ctx.pinned_ids:
                result.pinned_skipped += 1
                continue
            if ep.id in {eid for s in ctx.summaries for eid in s.source_episode_ids}:
                result.referenced_skipped += 1
                continue
            should_forget, reason = False, ""
            for policy in self._policies:
                decision, r = policy.should_forget(ep, ctx)
                if decision:
                    should_forget = True
                    reason = r
                    break
            if should_forget:
                batch.append(ep)
                if not dry_run:
                    ctx.episode_store.delete(ep.id)
                result.episodes_removed += 1
                result.details.append(
                    ForgettingEvent(
                        record_id=ep.id,
                        record_type="episode",
                        reason=reason,
                        policy=self._policies[0].name() if self._policies else "unknown",
                        timestamp=datetime.now(UTC).isoformat(),
                        importance=ep.importance,
                        age_days=_age_seconds(ep.timestamp) / ONE_DAY,
                    ),
                )
            if len(batch) >= self._batch_size:
                break
        return result

    def _evaluate_facts(self, result: ForgettingResult, ctx: ForgettingContext, dry_run: bool) -> ForgettingResult:
        if not self._semantic_store:
            return result
        facts = self._semantic_store.search(text="", k=10000)
        for fact in facts:
            if fact.id in ctx.protected_ids:
                result.protected_skipped += 1
                continue
            if fact.id in ctx.pinned_ids:
                result.pinned_skipped += 1
                continue
            should_forget, reason = False, ""
            for policy in self._policies:
                decision, r = policy.should_forget(fact, ctx)
                if decision:
                    should_forget = True
                    reason = r
                    break
            if should_forget:
                if not dry_run:
                    self._semantic_store.delete(fact.id)
                result.facts_removed += 1
                result.details.append(
                    ForgettingEvent(
                        record_id=fact.id,
                        record_type="semantic_fact",
                        reason=reason,
                        policy=self._policies[0].name() if self._policies else "unknown",
                        timestamp=datetime.now(UTC).isoformat(),
                        importance=fact.importance,
                        age_days=0.0,
                    ),
                )
        return result

    def stats(self) -> dict[str, Any]:
        return {
            "episodes_total": self._episode_store.count(),
            "facts_total": self._semantic_store.count() if self._semantic_store else 0,
            "protected": self._protection.count_protected(),
            "pinned": self._protection.count_pinned(),
            "policies": [p.name() for p in self._policies],
        }


class ForgettingScheduler:
    def __init__(self, engine: ForgettingEngine) -> None:
        self._engine = engine
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def run_once(self, dry_run: bool = False) -> ForgettingResult:
        return self._engine.run(dry_run=dry_run)
