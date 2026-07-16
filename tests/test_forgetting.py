from __future__ import annotations

# ruff: noqa: SLF001
from datetime import UTC, datetime, timedelta

from motor.intelligence.memory.compression import SummaryRecord
from motor.intelligence.memory.episodic import Episode, EpisodeStore
from motor.intelligence.memory.forgetting import (
    ConfidenceForgetPolicy,
    ForgettingEngine,
    ForgettingScheduler,
    HybridForgetPolicy,
    ImportanceForgetPolicy,
    NeverForgetPolicy,
    ProtectionRules,
    TTLForgetPolicy,
)
from motor.intelligence.memory.semantic import SemanticFact, SemanticMemoryStore

ONE_DAY = 86400


def _store_episodes(store: EpisodeStore, count: int, **kwargs) -> None:
    for i in range(count):
        store.store(Episode(payload=f"e{i}", **kwargs))


class TestProtectionRules:
    def test_protect(self):
        pr = ProtectionRules()
        pr.protect("e1")
        assert pr.is_protected("e1")
        assert not pr.is_pinned("e1")

    def test_pin(self):
        pr = ProtectionRules()
        pr.pin("e2")
        assert pr.is_pinned("e2")

    def test_unprotect(self):
        pr = ProtectionRules()
        pr.protect("e1")
        assert pr.unprotect("e1")
        assert not pr.is_protected("e1")


class TestTTLForgetPolicy:
    def test_expired_episode(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        eid = store.store(Episode(timestamp=past, ttl=ONE_DAY))
        ep = store._episodes.get(eid)
        policy = TTLForgetPolicy()
        from motor.intelligence.memory.forgetting import ForgettingContext

        ctx = ForgettingContext(store, SemanticMemoryStore(), [], set(), set())
        should, _ = policy.should_forget(ep, ctx)
        assert should

    def test_fresh_episode(self):
        store = EpisodeStore()
        eid = store.store(Episode(ttl=ONE_DAY * 30))
        ep = store._episodes.get(eid)
        policy = TTLForgetPolicy()
        ctx = ForgettingContext(store, SemanticMemoryStore(), [], set(), set())
        should, _ = policy.should_forget(ep, ctx)
        assert not should

    def test_semantic_fact(self):
        fact = SemanticFact(subject="s", predicate="p", object_value="o")
        policy = TTLForgetPolicy()
        from motor.intelligence.memory.forgetting import ForgettingContext

        ctx = ForgettingContext(EpisodeStore(), SemanticMemoryStore(), [], set(), set())
        should, _ = policy.should_forget(fact, ctx)
        assert not should


class TestImportanceForgetPolicy:
    def test_low_importance_old(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        eid = store.store(Episode(timestamp=past, importance=0.1, ttl=ONE_DAY * 90))
        ep = store._episodes.get(eid)
        policy = ImportanceForgetPolicy(min_importance=0.2, min_age_days=30)
        ctx = ForgettingContext(store, SemanticMemoryStore(), [], set(), set())
        should, _ = policy.should_forget(ep, ctx)
        assert should

    def test_high_importance_kept(self):
        store = EpisodeStore()
        eid = store.store(Episode(importance=0.9))
        ep = store._episodes.get(eid)
        policy = ImportanceForgetPolicy(min_importance=0.2)
        ctx = ForgettingContext(store, SemanticMemoryStore(), [], set(), set())
        should, _ = policy.should_forget(ep, ctx)
        assert not should


from motor.intelligence.memory.forgetting import ForgettingContext


class TestConfidenceForgetPolicy:
    def test_low_confidence(self):
        store = EpisodeStore()
        eid = store.store(Episode(confidence=0.1))
        ep = store._episodes.get(eid)
        policy = ConfidenceForgetPolicy(min_confidence=0.3)
        ctx = ForgettingContext(store, SemanticMemoryStore(), [], set(), set())
        should, _ = policy.should_forget(ep, ctx)
        assert should

    def test_high_confidence_kept(self):
        store = EpisodeStore()
        eid = store.store(Episode(confidence=0.9))
        ep = store._episodes.get(eid)
        policy = ConfidenceForgetPolicy(min_confidence=0.3)
        ctx = ForgettingContext(store, SemanticMemoryStore(), [], set(), set())
        should, _ = policy.should_forget(ep, ctx)
        assert not should


class TestHybridForgetPolicy:
    def test_ttl_or_importance(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        eid = store.store(Episode(timestamp=past, importance=0.9, ttl=ONE_DAY, confidence=0.9))
        ep = store._episodes.get(eid)
        policy = HybridForgetPolicy(require_all=False)
        ctx = ForgettingContext(store, SemanticMemoryStore(), [], set(), set())
        should, _ = policy.should_forget(ep, ctx)
        assert should  # TTL expired

    def test_require_all(self):
        store = EpisodeStore()
        eid = store.store(Episode(importance=0.9, confidence=0.9, ttl=ONE_DAY * 90))
        ep = store._episodes.get(eid)
        policy = HybridForgetPolicy(require_all=True)
        ctx = ForgettingContext(store, SemanticMemoryStore(), [], set(), set())
        should, _ = policy.should_forget(ep, ctx)
        assert not should  # all conditions must be met

    def test_never_policy(self):
        policy = NeverForgetPolicy()
        ctx = ForgettingContext(EpisodeStore(), SemanticMemoryStore(), [], set(), set())
        should, _ = policy.should_forget(None, ctx)
        assert not should


class TestForgettingEngine:
    def test_engine_empty(self):
        engine = ForgettingEngine(EpisodeStore(), SemanticMemoryStore(), policies=[NeverForgetPolicy()])
        result = engine.run()
        assert result.total_removed == 0

    def test_engine_removes_expired(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        store.store(Episode(timestamp=past, ttl=86400 * 30, payload="old", confidence=0.1))
        store.store(Episode(payload="fresh"))
        engine = ForgettingEngine(store, SemanticMemoryStore(), policies=[ConfidenceForgetPolicy(min_confidence=0.3)])
        result = engine.run()
        assert result.episodes_removed >= 1
        assert store.count() == 1

    def test_dry_run(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        store.store(Episode(timestamp=past, ttl=ONE_DAY, payload="old"))
        engine = ForgettingEngine(store, SemanticMemoryStore(), policies=[TTLForgetPolicy()])
        result = engine.run(dry_run=True)
        assert result.episodes_removed >= 1
        assert result.dry_run
        assert store.count() == 1  # not actually deleted

    def test_protected_skipped(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        eid = store.store(Episode(timestamp=past, ttl=ONE_DAY, payload="old"))
        pr = ProtectionRules()
        pr.protect(eid)
        engine = ForgettingEngine(store, SemanticMemoryStore(), policies=[TTLForgetPolicy()], protection=pr)
        result = engine.run()
        assert result.protected_skipped >= 1
        assert result.episodes_removed == 0

    def test_pinned_skipped(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        eid = store.store(Episode(timestamp=past, ttl=ONE_DAY, payload="old"))
        pr = ProtectionRules()
        pr.pin(eid)
        engine = ForgettingEngine(store, SemanticMemoryStore(), policies=[TTLForgetPolicy()], protection=pr)
        result = engine.run()
        assert result.pinned_skipped >= 1
        assert result.episodes_removed == 0

    def test_referenced_skipped(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        eid = store.store(Episode(timestamp=past, ttl=ONE_DAY, payload="old"))
        summary = SummaryRecord(source_episode_ids=[eid], summary="test")
        engine = ForgettingEngine(store, SemanticMemoryStore(), summaries=[summary], policies=[TTLForgetPolicy()])
        result = engine.run()
        assert result.referenced_skipped >= 1
        assert result.episodes_removed == 0

    def test_facts_removed(self):
        sstore = SemanticMemoryStore()
        sstore.store(SemanticFact(subject="s", predicate="p", object_value="o", confidence=0.1))
        engine = ForgettingEngine(EpisodeStore(), sstore, policies=[ConfidenceForgetPolicy(min_confidence=0.3)])
        result = engine.run()
        assert result.facts_removed >= 1

    def test_simulate(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        store.store(Episode(timestamp=past, ttl=ONE_DAY, payload="old"))
        engine = ForgettingEngine(store, SemanticMemoryStore(), policies=[TTLForgetPolicy()])
        result = engine.simulate()
        assert result.episodes_removed >= 1
        assert result.dry_run
        assert store.count() == 1

    def test_stats(self):
        engine = ForgettingEngine(EpisodeStore(), SemanticMemoryStore())
        stats = engine.stats()
        assert "episodes_total" in stats
        assert "policies" in stats

    def test_idempotent(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        store.store(Episode(timestamp=past, ttl=ONE_DAY, payload="old"))
        store.store(Episode(payload="fresh"))
        engine = ForgettingEngine(store, SemanticMemoryStore(), policies=[TTLForgetPolicy()])
        engine.run()
        r2 = engine.run()
        assert r2.total_removed == 0  # already cleaned


class TestForgettingScheduler:
    def test_enable_disable(self):
        engine = ForgettingEngine(EpisodeStore(), SemanticMemoryStore())
        scheduler = ForgettingScheduler(engine)
        assert not scheduler.enabled
        scheduler.enable()
        assert scheduler.enabled
        scheduler.disable()
        assert not scheduler.enabled

    def test_run_once(self):
        engine = ForgettingEngine(EpisodeStore(), SemanticMemoryStore())
        scheduler = ForgettingScheduler(engine)
        result = scheduler.run_once()
        assert result.total_removed == 0

    def test_run_once_dry_run(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        store.store(Episode(timestamp=past, ttl=ONE_DAY, payload="old"))
        engine = ForgettingEngine(store, SemanticMemoryStore(), policies=[TTLForgetPolicy()])
        scheduler = ForgettingScheduler(engine)
        result = scheduler.run_once(dry_run=True)
        assert result.episodes_removed >= 1


class TestForgettingBenchmark:
    def test_under_500ms(self):
        import time

        store = EpisodeStore()
        for i in range(500):
            ts = (datetime.now(UTC) - timedelta(days=i % 10)).isoformat()
            store.store(Episode(timestamp=ts, ttl=ONE_DAY if i % 2 == 0 else ONE_DAY * 90, payload=f"e{i}"))
        engine = ForgettingEngine(store, SemanticMemoryStore(), policies=[TTLForgetPolicy()])
        start = time.monotonic()
        engine.run()
        elapsed = (time.monotonic() - start) * 1000
        assert elapsed < 500, f"Took {elapsed:.1f}ms"


class TestForgettingResult:
    def test_total_removed(self):
        from motor.intelligence.memory.forgetting import ForgettingResult

        r = ForgettingResult(episodes_removed=3, facts_removed=2)
        assert r.total_removed == 5
