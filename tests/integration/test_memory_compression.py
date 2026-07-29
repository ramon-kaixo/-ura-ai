from __future__ import annotations

from datetime import UTC, datetime, timedelta

from motor.intelligence.memory.compression import (
    AgeBasedCompression,
    CompressionResult,
    CompressionScheduler,
    HybridCompressionPolicy,
    MemoryCompressor,
    NeverCompress,
    SizeBasedCompression,
)
from motor.intelligence.memory.episodic import Episode, EpisodeStore


def _store_episodes(store: EpisodeStore, count: int, session: str = "s1") -> None:
    for i in range(count):
        store.store(Episode(payload=f"Episode {i} content", session_id=session))


class TestNeverCompress:
    def test_never_runs(self):
        store = EpisodeStore()
        _store_episodes(store, 100)
        policy = NeverCompress()
        compressor = MemoryCompressor(store, policy)
        result = compressor.compress()
        assert result.summaries_created == 0
        assert result.episodes_compressed == 0


class TestSizeBasedCompression:
    def test_below_threshold(self):
        store = EpisodeStore()
        _store_episodes(store, 10)
        policy = SizeBasedCompression(max_episodes=100)
        compressor = MemoryCompressor(store, policy)
        result = compressor.compress()
        assert result.summaries_created == 0

    def test_above_threshold(self):
        store = EpisodeStore()
        _store_episodes(store, 50)
        policy = SizeBasedCompression(max_episodes=10)
        compressor = MemoryCompressor(store, policy)
        result = compressor.compress()
        assert result.summaries_created >= 1
        assert result.episodes_compressed >= 1

    def test_delete_originals(self):
        store = EpisodeStore()
        _store_episodes(store, 50)
        policy = SizeBasedCompression(max_episodes=10, delete_after_compress=True)
        compressor = MemoryCompressor(store, policy)
        count_before = store.count()
        result = compressor.compress()
        assert result.episodes_deleted > 0
        assert store.count() < count_before

    def test_keep_originals(self):
        store = EpisodeStore()
        _store_episodes(store, 50)
        policy = SizeBasedCompression(max_episodes=10, delete_after_compress=False)
        compressor = MemoryCompressor(store, policy)
        count_before = store.count()
        compressor.compress()
        assert store.count() == count_before  # kept


class TestAgeBasedCompression:
    def test_recent_not_compressed(self):
        store = EpisodeStore()
        _store_episodes(store, 10)
        policy = AgeBasedCompression(max_age_days=7)
        compressor = MemoryCompressor(store, policy)
        result = compressor.compress()
        assert result.summaries_created == 0

    def test_old_episodes_compressed(self):
        store = EpisodeStore()
        old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        store.store(Episode(timestamp=old, payload="Old content", ttl=86400 * 30))
        store.store(Episode(payload="Recent content"))
        policy = AgeBasedCompression(max_age_days=7)
        compressor = MemoryCompressor(store, policy)
        result = compressor.compress()
        assert result.summaries_created >= 1
        assert result.episodes_compressed >= 1


class TestHybridCompressionPolicy:
    def test_combines_age_and_size(self):
        store = EpisodeStore()
        old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        for i in range(30):
            store.store(Episode(timestamp=old, payload=f"Old {i}", ttl=86400 * 30))
        policy = HybridCompressionPolicy(max_age_days=7, max_episodes=20)
        compressor = MemoryCompressor(store, policy)
        result = compressor.compress()
        assert result.summaries_created >= 1


class TestSummaryRecord:
    def test_auto_id(self):
        from motor.intelligence.memory.compression import SummaryRecord

        sr = SummaryRecord(source_episode_ids=["e1"], summary="test")
        assert sr.id != ""
        assert sr.created_at != ""


class TestCompressionResult:
    def test_defaults(self):
        r = CompressionResult()
        assert r.summaries_created == 0
        assert r.episodes_compressed == 0


class TestMemoryCompressor:
    def test_compress_empty_store(self):
        store = EpisodeStore()
        compressor = MemoryCompressor(store)
        result = compressor.compress()
        assert result.summaries_created == 0

    def test_summary_has_references(self):
        store = EpisodeStore()
        for i in range(20):
            store.store(Episode(payload=f"Episode {i}", session_id="s1"))
        policy = SizeBasedCompression(max_episodes=5)
        compressor = MemoryCompressor(store, policy)
        result = compressor.compress()
        assert result.summaries_created >= 1
        summaries = compressor.get_summaries()
        assert len(summaries) >= 1
        assert len(summaries[0].source_episode_ids) > 0

    def test_summary_content(self):
        store = EpisodeStore()
        store.store(Episode(payload="Hello world", session_id="s1"))
        store.store(Episode(payload="Second message", session_id="s1"))
        policy = SizeBasedCompression(max_episodes=0)
        compressor = MemoryCompressor(store, policy)
        compressor.compress()
        summaries = compressor.get_summaries()
        assert len(summaries) >= 1
        assert "Hello" in summaries[0].summary or "Second" in summaries[0].summary

    def test_multiple_sessions(self):
        store = EpisodeStore()
        for i in range(10):
            store.store(Episode(payload=f"A{i}", session_id="s1"))
            store.store(Episode(payload=f"B{i}", session_id="s2"))
        policy = SizeBasedCompression(max_episodes=5)
        compressor = MemoryCompressor(store, policy)
        result = compressor.compress()
        assert result.summaries_created >= 2  # one per session

    def test_summary_confidence_and_importance(self):
        store = EpisodeStore()
        store.store(Episode(payload="A", session_id="s1", importance=0.9, confidence=0.8))
        store.store(Episode(payload="B", session_id="s1", importance=0.5, confidence=0.4))
        policy = SizeBasedCompression(max_episodes=0)
        compressor = MemoryCompressor(store, policy)
        compressor.compress()
        summaries = compressor.get_summaries()
        assert summaries[0].confidence > 0
        assert summaries[0].importance > 0

    def test_policy_swappable(self):
        store = EpisodeStore()
        _store_episodes(store, 50)
        compressor = MemoryCompressor(store, NeverCompress())
        assert compressor.compress().summaries_created == 0
        compressor.policy = SizeBasedCompression(max_episodes=10)
        assert compressor.compress().summaries_created >= 1

    def test_idempotent(self):
        store = EpisodeStore()
        _store_episodes(store, 50)
        policy = SizeBasedCompression(max_episodes=10)
        compressor = MemoryCompressor(store, policy)
        r1 = compressor.compress()
        r2 = compressor.compress()
        # Second run should produce fewer or no new summaries
        assert r2.summaries_created <= r1.summaries_created

    def test_get_summary_by_id(self):
        store = EpisodeStore()
        _store_episodes(store, 50)
        policy = SizeBasedCompression(max_episodes=10)
        compressor = MemoryCompressor(store, policy)
        compressor.compress()
        summaries = compressor.get_summaries()
        if summaries:
            sid = summaries[0].id
            assert compressor.get_summary(sid) is not None

    def test_clear_summaries(self):
        store = EpisodeStore()
        _store_episodes(store, 50)
        policy = SizeBasedCompression(max_episodes=10)
        compressor = MemoryCompressor(store, policy)
        compressor.compress()
        assert compressor.count_summaries() > 0
        assert compressor.clear_summaries() > 0
        assert compressor.count_summaries() == 0

    def test_summary_tags(self):
        store = EpisodeStore()
        store.store(Episode(payload="A", session_id="s1", tags=["urgent", "bug"]))
        store.store(Episode(payload="B", session_id="s1", tags=["info"]))
        policy = SizeBasedCompression(max_episodes=0)
        compressor = MemoryCompressor(store, policy)
        compressor.compress()
        summaries = compressor.get_summaries()
        assert "urgent" in summaries[0].tags
        assert "bug" in summaries[0].tags
        assert "info" in summaries[0].tags


class TestCompressionScheduler:
    def test_enable_disable(self):
        store = EpisodeStore()
        compressor = MemoryCompressor(store)
        scheduler = CompressionScheduler(compressor)
        assert not scheduler.enabled
        scheduler.enable()
        assert scheduler.enabled
        scheduler.disable()
        assert not scheduler.enabled

    def test_run_once(self):
        store = EpisodeStore()
        _store_episodes(store, 50)
        compressor = MemoryCompressor(store, SizeBasedCompression(max_episodes=10))
        scheduler = CompressionScheduler(compressor)
        result = scheduler.run_once()
        assert isinstance(result, CompressionResult)


class TestCompressionBenchmark:
    def test_compression_under_500ms(self):
        import time

        store = EpisodeStore()
        for i in range(500):
            store.store(Episode(payload=f"Episode {i} content", session_id=f"s{i % 5}"))
        compressor = MemoryCompressor(store, SizeBasedCompression(max_episodes=100))
        start = time.monotonic()
        compressor.compress()
        elapsed = (time.monotonic() - start) * 1000
        assert elapsed < 500, f"Compression took {elapsed:.1f}ms > 500ms"


class TestThreadSafety:
    def test_concurrent_compress(self):
        import concurrent.futures

        store = EpisodeStore()
        for i in range(100):
            store.store(Episode(payload=f"E{i}", session_id=f"s{i % 3}"))
        compressor = MemoryCompressor(store, SizeBasedCompression(max_episodes=50))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as exe:
            futures = [exe.submit(compressor.compress) for _ in range(5)]
            concurrent.futures.wait(futures)
        for f in futures:
            assert isinstance(f.result(), CompressionResult)
