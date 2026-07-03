"""Tests para VectorAugmentedRetriever."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from knowledge.engine.models import AssetSource, KnowledgeAsset
from knowledge.engine.vector_base import VectorResult
from knowledge.engine.vector_retriever import VectorAugmentedRetriever


@dataclass
class FakeRetrievalResult:
    """Simula RetrievalResult de GraphRetriever."""

    asset_id: str
    score: float = 0.0
    title: str = ""
    kind: str = ""
    snippet: str = ""
    metadata: dict = field(default_factory=dict)


def _make_asset(asset_id: str, title: str = "") -> KnowledgeAsset:
    return KnowledgeAsset(
        asset_id=asset_id,
        asset_type="pdf",  # type: ignore[arg-type]
        metadata={"title": title} if title else {},
        source=AssetSource(kind="test", location=""),
        quality=1.0,
    )


@pytest.fixture
def mock_graph():
    g = MagicMock()
    g.retrieve_assets.return_value = [
        FakeRetrievalResult(asset_id="a1", score=0.9),
        FakeRetrievalResult(asset_id="a2", score=0.8),
    ]
    return g


@pytest.fixture
def mock_asset_store():
    s = MagicMock()
    assets = {
        "a1": _make_asset("a1", "Alpha"),
        "a2": _make_asset("a2", "Beta"),
        "a3": _make_asset("a3", "Gamma"),
        "a4": _make_asset("a4", "Delta"),
    }
    s.get_asset.side_effect = assets.get
    return s


@pytest.fixture
def mock_embedder():
    e = MagicMock()
    e.available = True
    e.embed_query.return_value = [0.1, 0.2, 0.3]
    return e


@pytest.fixture
def mock_vector_store():
    vs = MagicMock()
    vs.available = True
    vs.search.return_value = [
        VectorResult(asset_id="a3", score=0.95),
        VectorResult(asset_id="a4", score=0.85),
    ]
    return vs


class TestVectorAugmentedRetrieverHeuristicOnly:
    """Sin embedder ni vector_store — solo búsqueda heurística."""

    def test_retrieves_heuristic_results(self, mock_graph, mock_asset_store):
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store)
        result = r.retrieve_assets("test query")
        mock_graph.retrieve_assets.assert_called_once()
        assert len(result) == 2
        assert result[0].asset_id == "a1"
        assert result[1].asset_id == "a2"

    def test_use_vector_flag_ignored_when_no_backend(self, mock_graph, mock_asset_store):
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store)
        result = r.retrieve_assets("test query", use_vector=True)
        assert len(result) == 2

    def test_embedder_present_but_vector_disabled(self, mock_graph, mock_asset_store, mock_embedder):
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store, embedder=mock_embedder)
        result = r.retrieve_assets("test query", use_vector=False)
        assert len(result) == 2
        mock_embedder.embed_query.assert_not_called()

    def test_store_present_but_vector_disabled(self, mock_graph, mock_asset_store, mock_vector_store):
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store, vector_store=mock_vector_store)
        result = r.retrieve_assets("test query", use_vector=False)
        assert len(result) == 2
        mock_vector_store.search.assert_not_called()

    def test_embedder_not_available_fallback(self, mock_graph, mock_asset_store, mock_embedder):
        mock_embedder.available = False
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store, embedder=mock_embedder)
        result = r.retrieve_assets("test query", use_vector=True)
        assert len(result) == 2

    def test_store_not_available_fallback(self, mock_graph, mock_asset_store, mock_vector_store):
        mock_vector_store.available = False
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store, vector_store=mock_vector_store)
        result = r.retrieve_assets("test query", use_vector=True)
        assert len(result) == 2

    def test_empty_heuristic_results(self, mock_graph, mock_asset_store):
        mock_graph.retrieve_assets.return_value = []
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store)
        result = r.retrieve_assets("test query")
        assert len(result) == 0

    def test_asset_store_returns_none_skipped(self, mock_graph, mock_asset_store):
        mock_graph.retrieve_assets.return_value = [
            FakeRetrievalResult(asset_id="nonexistent"),
        ]
        mock_asset_store.get_asset.return_value = None
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store)
        result = r.retrieve_assets("test query")
        assert len(result) == 0

    def test_passes_asset_type_to_graph(self, mock_graph, mock_asset_store):
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store)
        r.retrieve_assets("test query", asset_type="pdf")  # type: ignore[arg-type]
        mock_graph.retrieve_assets.assert_called_with("test query", limit=10, asset_type="pdf")

    def test_respects_limit(self, mock_graph, mock_asset_store):
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store)
        result = r.retrieve_assets("test query", limit=1)
        assert len(result) == 1

    def test_rrf_k_custom(self, mock_graph, mock_asset_store):
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store, rrf_k=1)
        result = r.retrieve_assets("test query")
        assert len(result) == 2


class TestVectorAugmentedRetrieverVectorEnabled:
    """Con embedder + vector_store — RRF fusiona resultados."""

    def test_rrf_fuses_heuristic_and_vector(self, mock_graph, mock_asset_store, mock_embedder, mock_vector_store):
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store, mock_embedder, mock_vector_store)
        result = r.retrieve_assets("test query", use_vector=True)
        # Ambos resultados deben estar presentes
        ids = {a.asset_id for a in result}
        assert "a1" in ids
        assert "a2" in ids
        assert "a3" in ids
        assert "a4" in ids

    def test_vector_search_failure_fallback(self, mock_graph, mock_asset_store, mock_embedder, mock_vector_store):
        mock_vector_store.search.side_effect = RuntimeError("Qdrant timeout")
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store, mock_embedder, mock_vector_store)
        result = r.retrieve_assets("test query", use_vector=True)
        # Solo heurístico
        assert len(result) == 2
        assert result[0].asset_id == "a1"

    def test_embed_query_failure_fallback(self, mock_graph, mock_asset_store, mock_embedder, mock_vector_store):
        mock_embedder.embed_query.side_effect = RuntimeError("Ollama down")
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store, mock_embedder, mock_vector_store)
        result = r.retrieve_assets("test query", use_vector=True)
        assert len(result) == 2

    def test_rrf_same_asset_in_both(self, mock_graph, mock_asset_store, mock_embedder, mock_vector_store):
        """Mismo asset_id aparece en heurístico y vectorial — score sumado."""
        mock_graph.retrieve_assets.return_value = [
            FakeRetrievalResult(asset_id="a1", score=0.9),
        ]
        mock_vector_store.search.return_value = [
            VectorResult(asset_id="a1", score=0.95),
        ]
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store, mock_embedder, mock_vector_store)
        result = r.retrieve_assets("test query", use_vector=True)
        assert len(result) == 1
        assert result[0].asset_id == "a1"

    def test_missing_asset_in_store_skipped(self, mock_graph, mock_asset_store, mock_embedder, mock_vector_store):
        mock_asset_store.get_asset.side_effect = lambda aid: _make_asset(aid) if aid != "a3" else None
        mock_vector_store.search.return_value = [
            VectorResult(asset_id="a3", score=0.95),
            VectorResult(asset_id="a4", score=0.85),
        ]
        r = VectorAugmentedRetriever(mock_graph, mock_asset_store, mock_embedder, mock_vector_store)
        result = r.retrieve_assets("test query", use_vector=True)
        ids = {a.asset_id for a in result}
        assert "a3" not in ids  # skipped
        assert "a4" in ids
