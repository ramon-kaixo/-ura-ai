"""Tests for vector_qdrant.py — QdrantVectorStore."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import httpx
import pytest

from knowledge.engine.vector_base import VectorItem
from knowledge.engine.vector_qdrant import QdrantVectorStore

if TYPE_CHECKING:
    from knowledge.engine.vector_base import VectorStore


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """Fixture que parchea httpx.Client y retorna la instancia mock."""
    with patch("knowledge.engine.vector_qdrant.httpx.Client") as m:
        instance = MagicMock()
        m.return_value = instance
        yield instance


def _health_response(*, ok: bool = True) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200 if ok else 503
    return resp


def _search_response(points: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"result": points}
    return resp


def _upsert_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"result": {"operation_id": 1, "status": "completed"}}
    return resp


def _count_response(count: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"result": {"count": count}}
    return resp


def _collection_response(*, created: bool = True) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200 if created else 409
    return resp


# ── Tests ───────────────────────────────────────────────────────────────────


class TestQdrantVectorStoreProtocol:
    """Verifica que QdrantVectorStore puede tratarse como VectorStore."""

    def test_is_vector_store(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        store: VectorStore = QdrantVectorStore(collection="test")
        assert isinstance(store, QdrantVectorStore)


class TestSearch:
    """Tests para search()."""

    def test_search_similar(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.post.return_value = _search_response(
            [
                {"id": "a", "score": 0.95, "payload": {"asset_id": "a"}},
                {"id": "b", "score": 0.80, "payload": {"asset_id": "b"}},
            ],
        )
        store = QdrantVectorStore(collection="test")
        results = store.search([1.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0].asset_id == "a"
        assert results[0].score == 0.95
        assert results[1].asset_id == "b"

    def test_search_empty(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.post.return_value = _search_response([])
        store = QdrantVectorStore(collection="test")
        assert store.search([1.0, 0.0]) == []

    def test_search_not_available(self, mock_client):
        store = QdrantVectorStore(collection="test")
        store._degraded = True  # noqa: SLF001
        assert store.search([1.0, 0.0]) == []

    def test_search_empty_vector(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        store = QdrantVectorStore(collection="test")
        assert store.search([]) == []

    def test_search_http_error(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.post.side_effect = httpx.HTTPError("Qdrant down")
        store = QdrantVectorStore(collection="test")
        assert store.search([1.0, 0.0]) == []
        assert store.available is False  # degraded

    def test_search_with_filter(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.post.return_value = _search_response(
            [
                {"id": "a", "score": 0.9, "payload": {"asset_id": "a"}},
            ],
        )
        store = QdrantVectorStore(collection="test")
        results = store.search([1.0, 0.0], filter={"asset_type": "pdf"})
        assert len(results) == 1
        # Verificar que el filter se tradujo al formato Qdrant
        call_args = mock_client.post.call_args
        assert call_args is not None
        body = call_args[1]["json"]
        assert "filter" in body
        assert body["filter"] == {
            "must": [{"key": "asset_type", "match": {"value": "pdf"}}],
        }


class TestUpsert:
    """Tests para upsert()."""

    def test_upsert_items(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.put.return_value = _upsert_response()
        store = QdrantVectorStore(collection="test")
        items = [VectorItem("a", [1.0, 0.0], "preview a")]
        count = store.upsert(items)
        assert count == 1

    def test_upsert_empty(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        store = QdrantVectorStore(collection="test")
        assert store.upsert([]) == 0

    def test_upsert_not_available(self, mock_client):
        store = QdrantVectorStore(collection="test")
        store._degraded = True  # noqa: SLF001
        assert store.upsert([VectorItem("a", [1.0], "x")]) == 0

    def test_upsert_auto_create_collection(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        # Primera llamada PUT = create collection (200)
        # Segunda llamada PUT = upsert points (200)
        mock_client.put.side_effect = [
            _collection_response(created=True),  # ensure_collection
            _upsert_response(),  # upsert points
        ]
        store = QdrantVectorStore(collection="new-collection")
        count = store.upsert([VectorItem("a", [1.0, 0.0], "x")])
        assert count == 1
        # Primera PUT debe haber sido para crear colección
        first_call = mock_client.put.call_args_list[0]
        assert "/collections/new-collection" in str(first_call)

    def test_upsert_collection_already_exists(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        # 409 = collection already exists (acceptable)
        mock_client.put.side_effect = [
            _collection_response(created=False),  # 409
            _upsert_response(),
        ]
        store = QdrantVectorStore(collection="existing")
        count = store.upsert([VectorItem("a", [1.0], "x")])
        assert count == 1

    def test_upsert_http_error(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.put.side_effect = httpx.HTTPError("Qdrant down")
        store = QdrantVectorStore(collection="test")
        assert store.upsert([VectorItem("a", [1.0], "x")]) == 0


class TestDelete:
    """Tests para delete()."""

    def test_delete(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.post.return_value = _upsert_response()  # delete returns similar
        store = QdrantVectorStore(collection="test")
        count = store.delete(["a", "b"])
        assert count == 2
        call_args = mock_client.post.call_args
        assert call_args is not None
        body = call_args[1]["json"]
        assert body["filter"]["must"][0]["has_id"] == ["a", "b"]

    def test_delete_empty(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        store = QdrantVectorStore(collection="test")
        assert store.delete([]) == 0

    def test_delete_not_available(self, mock_client):
        store = QdrantVectorStore(collection="test")
        store._degraded = True  # noqa: SLF001
        assert store.delete(["a"]) == 0

    def test_delete_http_error(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.post.side_effect = httpx.HTTPError("Qdrant down")
        store = QdrantVectorStore(collection="test")
        assert store.delete(["a"]) == 0
        assert store.available is False


class TestCount:
    """Tests para count()."""

    def test_count(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.post.return_value = _count_response(42)
        store = QdrantVectorStore(collection="test")
        assert store.count() == 42

    def test_count_empty(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.post.return_value = _count_response(0)
        store = QdrantVectorStore(collection="test")
        assert store.count() == 0

    def test_count_not_available(self, mock_client):
        store = QdrantVectorStore(collection="test")
        store._degraded = True  # noqa: SLF001
        assert store.count() == 0


class TestAvailable:
    """Tests para available property."""

    def test_available_true(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        store = QdrantVectorStore(collection="test")
        assert store.available is True

    def test_available_false(self, mock_client):
        store = QdrantVectorStore(collection="test")
        store._degraded = True  # noqa: SLF001
        assert store.available is False

    def test_available_http_error(self, mock_client):
        mock_client.get.side_effect = httpx.HTTPError("Connection refused")
        store = QdrantVectorStore(collection="test")
        store._degraded = True  # noqa: SLF001
        assert store.available is False
        # check_available does real HTTP check with backoff
        assert not store.check_available()

    def test_available_after_degraded(self, mock_client):
        mock_client.get.return_value = _health_response(ok=True)
        mock_client.post.side_effect = httpx.HTTPError("Qdrant down")
        store = QdrantVectorStore(collection="test")
        store.search([1.0])  # triggers degraded
        assert store.available is False
