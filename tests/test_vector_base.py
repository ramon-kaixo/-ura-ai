"""Tests for vector_base.py — Protocols, dataclasses, and structural typing."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from knowledge.engine.vector_base import Embedder, VectorItem, VectorResult, VectorStore

# ── Mock implementations for Protocol structural testing ────────────────────


class FakeEmbedder:
    """Implementa Embedder(Protocol) para tests."""

    def __init__(self, *, available: bool = True, vector_size: int = 768, max_input_tokens: int = 512):
        self._available = available
        self._vector_size = vector_size
        self._max_input_tokens = max_input_tokens
        self._cache: dict[str, list[float]] = {}

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._available:
            return []
        if not texts:
            return []
        results: list[list[float]] = []
        for t in texts:
            if t in self._cache:
                results.append(self._cache[t])
            else:
                vec = [float(hash(t) % 1000) / 1000.0 for _ in range(self._vector_size)]
                self._cache[t] = vec
                results.append(vec)
        return results

    def embed_query(self, text: str) -> list[float]:
        if not self._available:
            return []
        return self.embed([text])[0] if text else []

    @property
    def vector_size(self) -> int:
        return self._vector_size

    @property
    def max_input_tokens(self) -> int:
        return self._max_input_tokens

    @property
    def available(self) -> bool:
        return self._available


class FakeVectorStore:
    """Implementa VectorStore(Protocol) para tests."""

    def __init__(self, *, available: bool = True):
        self._available = available
        self._items: dict[str, list[float]] = {}
        self._previews: dict[str, str] = {}

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,  # noqa: A002
    ) -> list[VectorResult]:
        if not self._available:
            return []
        if not self._items:
            return []
        scored = [(aid, self._cosine_sim(query_vector, vec)) for aid, vec in self._items.items()]
        scored.sort(key=lambda x: -x[1])
        return [
            VectorResult(asset_id=aid, score=s, metadata={"text_preview": self._previews.get(aid, "")})
            for aid, s in scored[:top_k]
        ]

    def upsert(self, items: list[VectorItem]) -> int:
        if not self._available:
            return 0
        count = 0
        for item in items:
            self._items[item.asset_id] = item.vector
            self._previews[item.asset_id] = item.text_preview
            count += 1
        return count

    def delete(self, asset_ids: list[str]) -> int:
        if not self._available:
            return 0
        count = 0
        for aid in asset_ids:
            if aid in self._items:
                del self._items[aid]
                self._previews.pop(aid, None)
                count += 1
        return count

    def count(self) -> int:
        if not self._available:
            return 0
        return len(self._items)

    @property
    def available(self) -> bool:
        return self._available

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)


# ── Structural protocol compliance tests ───────────────────────────────────


class TestEmbedderProtocol:
    """Verifica que FakeEmbedder cumple Embedder(Protocol) estructuralmente."""

    def test_embed_texts(self):
        embedder: Embedder = FakeEmbedder()
        vectors = embedder.embed(["hello", "world"])
        assert len(vectors) == 2
        assert all(len(v) == 768 for v in vectors)

    def test_embed_empty(self):
        embedder: Embedder = FakeEmbedder()
        assert embedder.embed([]) == []

    def test_embed_not_available(self):
        embedder: Embedder = FakeEmbedder(available=False)
        assert embedder.embed(["test"]) == []

    def test_embed_cache_hit(self):
        embedder: Embedder = FakeEmbedder()
        v1 = embedder.embed(["hello"])
        v2 = embedder.embed(["hello"])
        assert v1 == v2

    def test_embed_query(self):
        embedder: Embedder = FakeEmbedder()
        vec = embedder.embed_query("test query")
        assert len(vec) == 768

    def test_embed_query_empty(self):
        embedder: Embedder = FakeEmbedder()
        vec = embedder.embed_query("")
        assert vec == []

    def test_embed_query_not_available(self):
        embedder: Embedder = FakeEmbedder(available=False)
        assert embedder.embed_query("test") == []

    def test_vector_size(self):
        embedder: Embedder = FakeEmbedder(vector_size=384)
        assert embedder.vector_size == 384

    def test_max_input_tokens(self):
        embedder: Embedder = FakeEmbedder(max_input_tokens=2048)
        assert embedder.max_input_tokens == 2048

    def test_max_input_tokens_unknown(self):
        embedder: Embedder = FakeEmbedder(max_input_tokens=0)
        assert embedder.max_input_tokens == 0

    def test_available_true(self):
        embedder: Embedder = FakeEmbedder(available=True)
        assert embedder.available is True

    def test_available_false(self):
        embedder: Embedder = FakeEmbedder(available=False)
        assert embedder.available is False


class TestVectorStoreProtocol:
    """Verifica que FakeVectorStore cumple VectorStore(Protocol) estructuralmente."""

    def test_search_similar(self):
        store: VectorStore = FakeVectorStore()
        store.upsert(
            [
                VectorItem("a", [1.0, 0.0], "doc a"),
                VectorItem("b", [0.0, 1.0], "doc b"),
            ]
        )
        results = store.search([1.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0].asset_id == "a"
        assert results[0].score >= results[1].score

    def test_search_empty(self):
        store: VectorStore = FakeVectorStore()
        assert store.search([1.0, 0.0]) == []

    def test_search_not_available(self):
        store: VectorStore = FakeVectorStore(available=False)
        assert store.search([1.0, 0.0]) == []

    def test_upsert_items(self):
        store: VectorStore = FakeVectorStore()
        count = store.upsert([VectorItem("a", [1.0, 0.0], "preview a")])
        assert count == 1
        assert store.count() == 1

    def test_upsert_empty(self):
        store: VectorStore = FakeVectorStore()
        assert store.upsert([]) == 0

    def test_upsert_not_available(self):
        store: VectorStore = FakeVectorStore(available=False)
        assert store.upsert([VectorItem("a", [1.0, 0.0], "x")]) == 0

    def test_upsert_duplicate(self):
        store: VectorStore = FakeVectorStore()
        store.upsert([VectorItem("a", [1.0, 0.0], "v1")])
        store.upsert([VectorItem("a", [0.0, 1.0], "v2")])
        assert store.count() == 1

    def test_delete(self):
        store: VectorStore = FakeVectorStore()
        store.upsert([VectorItem("a", [1.0, 0.0], "x")])
        assert store.delete(["a"]) == 1
        assert store.count() == 0

    def test_delete_nonexistent(self):
        store: VectorStore = FakeVectorStore()
        assert store.delete(["nonexistent"]) == 0

    def test_delete_empty(self):
        store: VectorStore = FakeVectorStore()
        assert store.delete([]) == 0

    def test_delete_not_available(self):
        store: VectorStore = FakeVectorStore(available=False)
        assert store.delete(["a"]) == 0

    def test_count(self):
        store: VectorStore = FakeVectorStore()
        assert store.count() == 0
        store.upsert([VectorItem("a", [1.0], "x"), VectorItem("b", [0.0], "y")])
        assert store.count() == 2

    def test_count_empty(self):
        store: VectorStore = FakeVectorStore()
        assert store.count() == 0

    def test_count_not_available(self):
        store: VectorStore = FakeVectorStore(available=False)
        assert store.count() == 0

    def test_count_after_ops(self):
        store: VectorStore = FakeVectorStore()
        store.upsert([VectorItem("a", [1.0], "x"), VectorItem("b", [0.0], "y")])
        store.delete(["a"])
        assert store.count() == 1

    def test_available_true(self):
        store: VectorStore = FakeVectorStore(available=True)
        assert store.available is True

    def test_available_false(self):
        store: VectorStore = FakeVectorStore(available=False)
        assert store.available is False

    def test_filter_flat_dict(self):
        store: VectorStore = FakeVectorStore()
        store.upsert([VectorItem("a", [1.0], "x")])
        results = store.search([1.0], filter={"asset_type": "pdf"})
        assert isinstance(results, list)


class TestVectorItem:
    """Verifica el dataclass VectorItem."""

    def test_fields(self):
        item = VectorItem(asset_id="abc", vector=[0.1, 0.2], text_preview="hello")
        assert item.asset_id == "abc"
        assert item.vector == [0.1, 0.2]
        assert item.text_preview == "hello"

    def test_frozen(self):
        item = VectorItem(asset_id="abc", vector=[0.1, 0.2], text_preview="hello")
        with pytest.raises(FrozenInstanceError):
            item.asset_id = "xyz"

    def test_equality(self):
        a = VectorItem("id", [1.0], "txt")
        b = VectorItem("id", [1.0], "txt")
        assert a == b

    def test_repr(self):
        item = VectorItem("id", [1.0], "txt")
        r = repr(item)
        assert "asset_id=" in r
        assert "vector=" in r
        assert "text_preview=" in r


class TestVectorResult:
    """Verifica el dataclass VectorResult."""

    def test_fields(self):
        r = VectorResult(asset_id="abc", score=0.95)
        assert r.asset_id == "abc"
        assert r.score == 0.95
        assert r.metadata == {}

    def test_mutable(self):
        r = VectorResult(asset_id="abc", score=0.95)
        r.metadata["key"] = "value"
        assert r.metadata["key"] == "value"

    def test_default_metadata(self):
        r = VectorResult(asset_id="abc", score=0.95)
        assert r.metadata == {}

    def test_custom_metadata(self):
        r = VectorResult(asset_id="abc", score=0.95, metadata={"type": "pdf"})
        assert r.metadata["type"] == "pdf"

    def test_equality(self):
        a = VectorResult("id", 0.9, {"k": "v"})
        b = VectorResult("id", 0.9, {"k": "v"})
        assert a == b


class TestDeterminism:
    """Verifica determinismo en embeddings mock."""

    def test_determinism_embed(self):
        e1: Embedder = FakeEmbedder(vector_size=768)
        e2: Embedder = FakeEmbedder(vector_size=768)
        texts = ["hello world", "test document", "repeated text", "hello world"]
        v1 = e1.embed(texts)
        v2 = e2.embed(texts)
        assert v1 == v2

    def test_determinism_embed_query(self):
        e1: Embedder = FakeEmbedder()
        e2: Embedder = FakeEmbedder()
        q = "same query every time"
        assert e1.embed_query(q) == e2.embed_query(q)

    def test_determinism_search(self):
        s1: VectorStore = FakeVectorStore()
        s2: VectorStore = FakeVectorStore()
        items = [VectorItem("a", [1.0, 0.0], "x"), VectorItem("b", [0.0, 1.0], "y")]
        s1.upsert(items)
        s2.upsert(items)
        qv = [1.0, 0.0]
        r1 = s1.search(qv)
        r2 = s2.search(qv)
        assert r1 == r2
