from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from motor.intelligence.memory.episodic import Episode, EpisodeStore
from motor.intelligence.memory.retrieval import (
    ContextQuery,
    ContextResult,
    ContextResultList,
    ContextRetriever,
)

ONE_DAY = 86400


def _make_store(episodes: list[Episode]) -> EpisodeStore:
    store = EpisodeStore()
    for ep in episodes:
        store.store(ep)
    return store


class TestContextQuery:
    def test_defaults(self):
        q = ContextQuery()
        assert q.text == ""
        assert q.session_id is None
        assert q.k == 10
        assert q.offset == 0
        assert q.weights is None

    def test_custom(self):
        q = ContextQuery(text="hello", session_id="s1", tags=["t1"], k=5)
        assert q.text == "hello"
        assert q.session_id == "s1"
        assert q.tags == ["t1"]
        assert q.k == 5


class TestContextResult:
    def test_explanation(self):
        r = ContextResult(
            episode=Episode(),
            semantic_score=0.8,
            recency_score=0.7,
            importance_score=0.6,
            confidence_score=0.5,
            score=0.65,
        )
        assert "sem=0.80" in r.explanation
        assert "rec=0.70" in r.explanation
        assert "imp=0.60" in r.explanation

    def test_explanation_no_semantic(self):
        r = ContextResult(episode=Episode(), recency_score=0.5, importance_score=0.5, confidence_score=0.5, score=0.5)
        assert "sem=" not in r.explanation


class TestContextResultList:
    def test_empty(self):
        rl = ContextResultList()
        assert len(rl) == 0
        assert rl.total == 0

    def test_with_results(self):
        rl = ContextResultList(results=[ContextResult(episode=Episode())], total=1)
        assert len(rl) == 1

    def test_to_dict(self):
        ep = Episode(payload="test content", session_id="s1")
        r = ContextResult(episode=ep, score=0.8)
        rl = ContextResultList(results=[r], total=1)
        d = rl.to_dict()
        assert d[0]["session_id"] == "s1"
        assert d[0]["score"] == 0.8


class TestContextRetrieverEmpty:
    def test_empty_store(self):
        store = EpisodeStore()
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery())
        assert len(results) == 0

    def test_empty_session(self):
        store = EpisodeStore()
        store.store(Episode(session_id="s1"))
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery(session_id="s2"))
        assert len(results) == 0


class TestContextRetrieverBySession:
    def test_single_session(self):
        store = EpisodeStore()
        store.store(Episode(session_id="s1", payload="a"))
        store.store(Episode(session_id="s1", payload="b"))
        store.store(Episode(session_id="s2", payload="c"))
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery(session_id="s1"))
        assert len(results) == 2
        assert {r.episode.payload for r in results} == {"a", "b"}


class TestContextRetrieverByTags:
    def test_tag_filter(self):
        store = EpisodeStore()
        store.store(Episode(tags=["urgent", "bug"], payload="a"))
        store.store(Episode(tags=["info"], payload="b"))
        store.store(Episode(tags=["urgent"], payload="c"))
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery(tags=["urgent"]))
        assert len(results) == 2

    def test_tag_matches_any(self):
        store = EpisodeStore()
        store.store(Episode(tags=["a"], payload="x"))
        store.store(Episode(tags=["b"], payload="y"))
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery(tags=["a", "b"]))
        assert len(results) == 2


class TestContextRetrieverRanking:
    def test_importance_ranking(self):
        store = EpisodeStore()
        store.store(Episode(payload="low", importance=0.2, confidence=0.5))
        store.store(Episode(payload="high", importance=0.9, confidence=0.5))
        retriever = ContextRetriever(store, weights={"semantic": 0, "recency": 0, "importance": 1.0, "confidence": 0})
        results = retriever.search(ContextQuery())
        assert results[0].episode.payload == "high"
        assert results[1].episode.payload == "low"

    def test_recency_ranking(self):
        store = EpisodeStore()
        now = datetime.now(UTC)
        old = (now - timedelta(hours=10)).isoformat()
        recent = (now - timedelta(minutes=5)).isoformat()
        store.store(Episode(timestamp=old, payload="old", importance=0.5, confidence=0.5))
        store.store(Episode(timestamp=recent, payload="recent", importance=0.5, confidence=0.5))
        retriever = ContextRetriever(store, weights={"semantic": 0, "recency": 1.0, "importance": 0, "confidence": 0})
        results = retriever.search(ContextQuery())
        assert results[0].episode.payload == "recent"

    def test_combined_ranking(self):
        store = EpisodeStore()
        now = datetime.now(UTC)
        # episode: high importance but old
        store.store(
            Episode(
                timestamp=(now - timedelta(hours=10)).isoformat(),
                payload="important_old",
                importance=0.9,
                confidence=0.5,
            ),
        )
        store.store(
            Episode(
                timestamp=(now - timedelta(minutes=5)).isoformat(),
                payload="medium_recent",
                importance=0.5,
                confidence=0.5,
            ),
        )
        store.store(
            Episode(
                timestamp=(now - timedelta(seconds=10)).isoformat(),
                payload="recent_low",
                importance=0.2,
                confidence=0.5,
            ),
        )
        # Default weights: recency=0.35, importance=0.35, confidence=0.30
        # With confidence equal, the combined score depends on recency + importance
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery())
        # All 3 should be returned
        assert len(results) == 3


class TestContextRetrieverLimits:
    def test_limit(self):
        store = EpisodeStore()
        for i in range(20):
            store.store(Episode(payload=f"e{i}"))
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery(k=5))
        assert len(results) == 5

    def test_offset(self):
        store = EpisodeStore()
        for i in range(20):
            store.store(Episode(payload=f"e{i}"))
        retriever = ContextRetriever(store)
        page1 = retriever.search(ContextQuery(k=5, offset=0))
        page2 = retriever.search(ContextQuery(k=5, offset=5))
        assert len(page1) == 5
        assert len(page2) == 5
        assert page1.results[0].episode.id != page2.results[0].episode.id


class TestContextRetrieverExpired:
    def test_expired_excluded(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=8)).isoformat()
        store.store(Episode(timestamp=past, ttl=ONE_DAY * 7, payload="expired"))
        store.store(Episode(payload="fresh"))
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery())
        assert len(results) == 1
        assert results[0].episode.payload == "fresh"

    def test_expired_auto_deleted(self):
        store = EpisodeStore()
        past = (datetime.now(UTC) - timedelta(days=8)).isoformat()
        eid = store.store(Episode(timestamp=past, ttl=ONE_DAY * 7, payload="gone"))
        assert store.get(eid) is None  # expired and deleted during search
        count_before = store.count()
        retriever = ContextRetriever(store)
        _ = retriever.search(ContextQuery())
        assert store.count() == count_before  # no change because already deleted


class TestContextRetrieverNoEmbedding:
    def test_no_embedding_graceful(self):
        store = EpisodeStore()
        store.store(Episode(payload="a", importance=0.9, confidence=0.9))
        # sem_weight=0 by default, so no semantic score is needed
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery(text="some query"))
        assert len(results) == 1

    def test_sem_weight_zero(self):
        store = EpisodeStore()
        store.store(Episode(payload="test"))
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery(text="test"))
        assert len(results) == 1


class TestContextRetrieverEdgeCases:
    def test_k_less_than_one(self):
        store = EpisodeStore()
        store.store(Episode())
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery(k=0))
        assert len(results) >= 1  # k defaults to 1 minimum

    def test_large_offset(self):
        store = EpisodeStore()
        store.store(Episode())
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery(k=10, offset=100))
        assert len(results) == 0

    def test_custom_weights(self):
        store = EpisodeStore()
        store.store(Episode(payload="a", importance=0.5, confidence=0.5))
        retriever = ContextRetriever(store)
        q = ContextQuery(weights={"semantic": 0, "recency": 0, "importance": 0.5, "confidence": 0.5})
        results = retriever.search(q)
        assert len(results) == 1

    def test_elapsed_ms(self):
        store = EpisodeStore()
        store.store(Episode())
        retriever = ContextRetriever(store)
        results = retriever.search(ContextQuery())
        assert results.elapsed_ms >= 0


class TestContextRetrieverBenchmark:
    def test_latency_under_50ms(self):
        store = EpisodeStore()
        for i in range(1000):
            store.store(Episode(payload=f"e{i}", importance=0.5, confidence=0.5))
        retriever = ContextRetriever(store)
        start = time.monotonic()
        for _ in range(10):
            retriever.search(ContextQuery(k=10))
        avg = (time.monotonic() - start) / 10 * 1000
        assert avg < 50, f"Avg latency {avg:.1f}ms > 50ms"


class TestContextRetrieverThreadSafety:
    def test_concurrent_search(self):
        import concurrent.futures

        store = EpisodeStore()
        for i in range(100):
            store.store(Episode(payload=f"e{i}", importance=0.5, confidence=0.5))
        retriever = ContextRetriever(store)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
            futures = [exe.submit(retriever.search, ContextQuery(k=5)) for _ in range(20)]
            concurrent.futures.wait(futures)
        for f in futures:
            assert len(f.result()) <= 5
