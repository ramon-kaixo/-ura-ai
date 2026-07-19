"""Tests para F14 bugs corregidos: F02, F03, F05."""

from __future__ import annotations

import tempfile
from pathlib import Path

from motor.intelligence.agents.runtime import MultiAgentRuntime
from motor.intelligence.memory.episodic import Episode, EpisodeStore, EpisodeStoreConfig
from motor.intelligence.retrieval.hybrid import HybridRetriever


class TestF14F02CancelWorkflow:
    """F14-F02: MultiAgentRuntime.cancel() workflow_id opcional."""

    def test_cancel_specific(self):
        runtime = MultiAgentRuntime()
        runtime._workflows["wf_test"] = {"status": "running"}
        result = runtime.cancel(workflow_id="wf_test")
        assert result is True
        assert runtime._workflows["wf_test"]["status"] == "cancelled"

    def test_cancel_all(self):
        runtime = MultiAgentRuntime()
        runtime._workflows["w1"] = {"status": "running"}
        runtime._workflows["w2"] = {"status": "running"}
        result = runtime.cancel()
        assert isinstance(result, int)
        assert result == 2

    def test_cancel_nonexistent(self):
        runtime = MultiAgentRuntime()
        result = runtime.cancel(workflow_id="nonexistent")
        assert result is False


class TestF14F03EpisodeStoreCorruption:
    """F14-F03: EpisodeStore se auto-recrea tras corrupción SQLite."""

    def test_corrupt_db_recreates(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
            f.write(b"CORRUPTED_DATA_NOT_SQLITE")

        try:
            config = EpisodeStoreConfig(persist_path=db_path)
            store = EpisodeStore(config=config)
            ep = Episode(session_id="s1", source="test", payload="data")
            store.store(ep)
            loaded = store.get_recent(k=10)
            assert len(loaded) >= 1
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_clean_db_works(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            config = EpisodeStoreConfig(persist_path=db_path)
            store = EpisodeStore(config=config)
            ep = Episode(session_id="s1", source="test", payload="hello")
            store.store(ep)
            loaded = store.get_recent(k=10)
            assert len(loaded) >= 1
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestF14F05HybridRetrieverFallback:
    """F14-F05: HybridRetriever cae gracefully sin Qdrant."""

    def test_vector_fails_uses_lexical(self):
        class FailingRetriever:
            def search(self, query: str, k: int = 10):
                raise ConnectionError("Qdrant not available")

        class OkRetriever:
            def search(self, query: str, k: int = 10):
                return [{"doc_id": "d1", "score": 0.9, "rank": 0}]

        hybrid = HybridRetriever(vector_retriever=FailingRetriever(), lexical_retriever=OkRetriever())
        results = hybrid.search("test", k=5)
        assert len(results) >= 1

    def test_both_fail_return_empty(self):
        class FailingRetriever:
            def search(self, query: str, k: int = 10):
                raise RuntimeError("Down")

        hybrid = HybridRetriever(vector_retriever=FailingRetriever(), lexical_retriever=FailingRetriever())
        results = hybrid.search("test", k=5)
        assert results == []

    def test_both_work_returns_fused(self):
        class SimpleRetriever:
            def search(self, query: str, k: int = 10):
                return [{"doc_id": "d1", "score": 0.8, "rank": 0}]

        hybrid = HybridRetriever(vector_retriever=SimpleRetriever(), lexical_retriever=SimpleRetriever())
        results = hybrid.search("test", k=5)
        assert len(results) == 1
