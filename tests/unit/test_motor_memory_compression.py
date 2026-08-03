"""Tests para motor.intelligence.memory.compression (MemoryCompressor, políticas)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import mock

from motor.intelligence.memory.compression import (
    AgeBasedCompression,
    CompressionResult,
    CompressionScheduler,
    HybridCompressionPolicy,
    MemoryCompressor,
    NeverCompress,
    SizeBasedCompression,
    SummaryRecord,
)
from motor.intelligence.memory.episodic import Episode


def _make_episode(**kwargs) -> Episode:
    defaults = {
        "id": "",
        "session_id": "sess-1",
        "timestamp": datetime.now(UTC).isoformat(),
        "source": "test",
        "payload": "contenido de ejemplo",
        "importance": 0.5,
        "confidence": 0.5,
        "tags": ["tag1"],
    }
    defaults.update(kwargs)
    return Episode(**defaults)


def _make_store(episodes: list[Episode]) -> mock.Mock:
    store = mock.Mock()
    store.get_recent.return_value = episodes
    store.count.return_value = len(episodes)
    return store


class TestSummaryRecord:
    def test_defaults_generate_id_and_timestamp(self):
        rec = SummaryRecord(source_episode_ids=["a"], summary="resumen")
        assert rec.id
        assert rec.created_at
        assert rec.tags == []
        assert rec.metadata == {}

    def test_explicit_id_and_created_at_preserved(self):
        rec = SummaryRecord(
            source_episode_ids=["a"],
            summary="resumen",
            id="custom-id",
            created_at="2026-01-01T00:00:00+00:00",
        )
        assert rec.id == "custom-id"
        assert rec.created_at == "2026-01-01T00:00:00+00:00"


class TestCompressionResult:
    def test_defaults(self):
        result = CompressionResult()
        assert result.summaries_created == 0
        assert result.episodes_compressed == 0
        assert result.episodes_deleted == 0
        assert result.elapsed_ms == 0.0
        assert result.errors == []


class TestNeverCompress:
    def test_never_runs(self):
        policy = NeverCompress()
        store = mock.Mock()
        assert policy.should_run(store) is False
        assert policy.select_candidates(store) == []
        assert policy.delete_originals is False


class TestAgeBasedCompression:
    def test_should_run_always_true(self):
        assert AgeBasedCompression().should_run(mock.Mock()) is True

    def test_select_filters_old_episodes(self):
        old = _make_episode(id="old", timestamp=(datetime.now(UTC) - timedelta(days=30)).isoformat())
        fresh = _make_episode(id="fresh", timestamp=datetime.now(UTC).isoformat())
        policy = AgeBasedCompression(max_age_days=7)
        candidates = policy.select_candidates(_make_store([old, fresh]))
        assert [c.id for c in candidates] == ["old"]

    def test_delete_originals_property(self):
        assert AgeBasedCompression().delete_originals is False
        assert AgeBasedCompression(delete_after_compress=True).delete_originals is True


class TestSizeBasedCompression:
    def test_should_run_over_limit(self):
        store = mock.Mock()
        store.count.return_value = 5001
        assert SizeBasedCompression(max_episodes=5000).should_run(store) is True
        store.count.return_value = 5000
        assert SizeBasedCompression(max_episodes=5000).should_run(store) is False

    def test_select_no_excess(self):
        episodes = [_make_episode(id=f"e{i}") for i in range(3)]
        policy = SizeBasedCompression(max_episodes=5)
        assert policy.select_candidates(_make_store(episodes)) == []

    def test_select_oldest_excess(self):
        episodes = [
            _make_episode(id="a", timestamp=(datetime.now(UTC) - timedelta(hours=3)).isoformat()),
            _make_episode(id="b", timestamp=(datetime.now(UTC) - timedelta(hours=2)).isoformat()),
            _make_episode(id="c", timestamp=(datetime.now(UTC) - timedelta(hours=1)).isoformat()),
        ]
        policy = SizeBasedCompression(max_episodes=1)
        candidates = policy.select_candidates(_make_store(episodes))
        assert [c.id for c in candidates] == ["a", "b"]

    def test_delete_originals_property(self):
        assert SizeBasedCompression().delete_originals is False
        assert SizeBasedCompression(delete_after_compress=True).delete_originals is True


class TestHybridCompressionPolicy:
    def test_should_run_short_circuit(self):
        policy = HybridCompressionPolicy()
        store = mock.Mock()
        with mock.patch.object(
            policy._age_policy, "should_run", return_value=True
        ), mock.patch.object(policy._size_policy, "should_run") as size_should:
            assert policy.should_run(store) is True
            size_should.assert_not_called()

    def test_should_run_false_when_both_false(self):
        policy = HybridCompressionPolicy(max_episodes=5000)
        store = mock.Mock()
        store.count.return_value = 10
        with mock.patch.object(policy._age_policy, "should_run", return_value=False):
            assert policy.should_run(store) is False

    def test_select_dedup_and_sort(self):
        old = _make_episode(id="dup", timestamp=(datetime.now(UTC) - timedelta(days=30)).isoformat())
        fresh = _make_episode(id="fresh", timestamp=datetime.now(UTC).isoformat())
        policy = HybridCompressionPolicy(max_age_days=7, max_episodes=0)
        store = mock.Mock()
        store.get_recent.return_value = [old, fresh, _make_episode(id="dup", timestamp=old.timestamp)]
        candidates = policy.select_candidates(store)
        assert [c.id for c in candidates] == ["dup", "fresh"]

    def test_delete_originals_property(self):
        assert HybridCompressionPolicy().delete_originals is False
        assert HybridCompressionPolicy(delete_after_compress=True).delete_originals is True


class TestMemoryCompressor:
    def test_default_policy_is_size_based(self):
        compressor = MemoryCompressor(store=mock.Mock())
        assert isinstance(compressor.policy, SizeBasedCompression)

    def test_policy_setter(self):
        compressor = MemoryCompressor(store=mock.Mock())
        policy = NeverCompress()
        compressor.policy = policy
        assert compressor.policy is policy

    def test_compress_skips_when_should_run_false(self):
        store = mock.Mock()
        compressor = MemoryCompressor(store=store, policy=NeverCompress())
        result = compressor.compress()
        assert result.summaries_created == 0
        assert result.elapsed_ms >= 0

    def test_compress_skips_when_no_candidates(self):
        store = mock.Mock()
        store.get_recent.return_value = []
        policy = mock.Mock()
        policy.should_run.return_value = True
        policy.select_candidates.return_value = []
        compressor = MemoryCompressor(store=store, policy=policy)
        result = compressor.compress()
        assert result.summaries_created == 0

    def test_compress_creates_summary(self):
        episodes = [_make_episode(id="e1", payload="mensaje uno"), _make_episode(id="e2", payload="mensaje dos")]
        store = _make_store(episodes)
        compressor = MemoryCompressor(store=store, policy=AgeBasedCompression(max_age_days=0))
        result = compressor.compress()
        assert result.summaries_created == 1
        assert result.episodes_compressed == 2
        assert result.errors == []
        assert compressor.count_summaries() == 1
        summary = compressor.get_summaries()[0]
        assert "mensaje uno" in summary.summary
        assert summary.metadata["session_id"] == "sess-1"
        assert summary.metadata["episode_count"] == 2
        assert summary.metadata["compression_ratio"] <= 1.0

    def test_compress_groups_by_session(self):
        episodes = [
            _make_episode(id="e1", session_id="sess-a", payload="a1"),
            _make_episode(id="e2", session_id="sess-b", payload="b1"),
            _make_episode(id="e3", session_id="sess-a", payload="a2"),
        ]
        compressor = MemoryCompressor(store=_make_store(episodes), policy=AgeBasedCompression(max_age_days=0))
        result = compressor.compress()
        assert result.summaries_created == 2
        assert compressor.count_summaries() == 2

    def test_compress_no_session_group(self):
        episodes = [_make_episode(id="e1", session_id="", payload="x")]
        compressor = MemoryCompressor(store=_make_store(episodes), policy=AgeBasedCompression(max_age_days=0))
        result = compressor.compress()
        assert result.summaries_created == 1
        summary = compressor.get_summaries()[0]
        assert summary.metadata["session_id"] == "_no_session"

    def test_compress_deletes_originals(self):
        episodes = [_make_episode(id="e1", payload="x"), _make_episode(id="e2", payload="y")]
        store = _make_store(episodes)
        compressor = MemoryCompressor(
            store=store, policy=AgeBasedCompression(max_age_days=0, delete_after_compress=True)
        )
        result = compressor.compress()
        assert result.episodes_deleted == 2
        assert store.delete.call_count == 2

    def test_compress_records_errors(self):
        policy = mock.Mock()
        policy.should_run.return_value = True
        policy.delete_originals = False
        policy.select_candidates.return_value = [_make_episode(id="e1", payload="x")]
        compressor = MemoryCompressor(store=mock.Mock(), policy=policy)
        with mock.patch.object(compressor, "_generate_summary", side_effect=RuntimeError("boom")):
            result = compressor.compress()
        assert len(result.errors) == 1
        assert "boom" in result.errors[0]
        assert result.summaries_created == 0

    def test_group_by_session_none(self):
        compressor = MemoryCompressor(store=mock.Mock())
        groups = compressor._group_by_session(
            [_make_episode(id="a", session_id="s1"), _make_episode(id="b", session_id="")]
        )
        assert set(groups) == {"s1", "_no_session"}

    def test_generate_summary_empty_returns_none(self):
        compressor = MemoryCompressor(store=mock.Mock())
        assert compressor._generate_summary("sess", []) is None

    def test_generate_summary_empty_payloads_returns_none(self):
        compressor = MemoryCompressor(store=mock.Mock())
        episodes = [_make_episode(id="a", payload=""), _make_episode(id="b", payload="")]
        assert compressor._generate_summary("sess", episodes) is None

    def test_generate_summary_dedup_and_truncate(self):
        compressor = MemoryCompressor(store=mock.Mock())
        payload = "x" * 500
        episodes = [
            _make_episode(id="a", payload=payload, tags=["t1"], importance=1.0, confidence=0.9),
            _make_episode(id="b", payload=payload, tags=["t2"], importance=0.0, confidence=0.1),
        ]
        summary = compressor._generate_summary("sess", episodes)
        assert summary is not None
        assert summary.summary.count("x") == 200
        assert summary.source_episode_ids == ["a", "b"]
        assert summary.confidence == 0.5
        assert summary.importance == 0.5
        assert summary.tags == ["t1", "t2"]

    def test_get_summaries_filters_and_limits(self):
        compressor = MemoryCompressor(store=mock.Mock())
        compressor._summaries = {
            f"s{i}": SummaryRecord(
                source_episode_ids=["a"],
                summary=f"s{i}",
                metadata={"session_id": "x" if i % 2 else "y"},
                created_at=f"2026-01-0{i+1}T00:00:00+00:00",
                id=f"s{i}",
            )
            for i in range(4)
        }
        filtered = compressor.get_summaries(session_id="x", k=1)
        assert len(filtered) == 1
        assert filtered[0].metadata["session_id"] == "x"
        assert len(compressor.get_summaries(k=2)) == 2
        assert len(compressor.get_summaries(k=100)) == 4

    def test_get_summary_by_id(self):
        compressor = MemoryCompressor(store=mock.Mock())
        rec = SummaryRecord(source_episode_ids=["a"], summary="s", id="abc")
        compressor._summaries["abc"] = rec
        assert compressor.get_summary("abc") is rec
        assert compressor.get_summary("nope") is None

    def test_clear_summaries(self):
        compressor = MemoryCompressor(store=mock.Mock())
        compressor._summaries = {
            "a": SummaryRecord(source_episode_ids=[], summary="s", id="a")
        }
        assert compressor.clear_summaries() == 1
        assert compressor.count_summaries() == 0


class TestCompressionScheduler:
    def test_enabled_toggle(self):
        scheduler = CompressionScheduler(compressor=mock.Mock())
        assert scheduler.enabled is False
        scheduler.enable()
        assert scheduler.enabled is True
        scheduler.disable()
        assert scheduler.enabled is False

    def test_run_once_delegates(self):
        compressor = mock.Mock()
        compressor.compress.return_value = CompressionResult(summaries_created=3)
        scheduler = CompressionScheduler(compressor=compressor)
        result = scheduler.run_once()
        assert result.summaries_created == 3
        compressor.compress.assert_called_once_with()
