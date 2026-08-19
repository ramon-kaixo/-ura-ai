"""Tests de cobertura para knowledge/engine/vector_base.py."""

from __future__ import annotations

from knowledge.engine.vector_base import Embedder, VectorItem, VectorResult, VectorStore


class FakeEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 3 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]

    @property
    def vector_size(self) -> int:
        return 3

    @property
    def max_input_tokens(self) -> int:
        return 512

    @property
    def available(self) -> bool:
        return True

    def check_available(self) -> bool:
        return True


class FakeStore:
    def __init__(self) -> None:
        self.items: dict[str, list[float]] = {}

    def search(self, query_vector: list[float], top_k: int = 10, filter: dict | None = None) -> list[VectorResult]:
        return [VectorResult(asset_id=k, score=0.5) for k in list(self.items)[:top_k]]

    def list_ids(self, limit: int = 100, offset: str | None = None) -> tuple[list[str], str | None]:
        ids = list(self.items)[offset or 0 : (offset or 0) + limit]
        return ids, None

    def upsert(self, items: list[VectorItem]) -> int:
        for i in items:
            self.items[i.asset_id] = i.vector
        return len(items)

    def delete(self, asset_ids: list[str]) -> int:
        n = 0
        for a in asset_ids:
            if a in self.items:
                del self.items[a]
                n += 1
        return n

    def count(self) -> int:
        return len(self.items)

    @property
    def available(self) -> bool:
        return True

    def check_available(self) -> bool:
        return True


def test_vector_item() -> None:
    item = VectorItem(asset_id="a1", vector=[0.1, 0.2], text_preview="preview")
    assert item.asset_id == "a1"
    assert item.vector == [0.1, 0.2]
    assert item.text_preview == "preview"


def test_vector_result_defaults() -> None:
    r = VectorResult(asset_id="a1", score=0.9)
    assert r.metadata == {}
    assert r.score == 0.9


def test_vector_result_con_metadata() -> None:
    r = VectorResult(asset_id="a1", score=0.5, metadata={"k": 1})
    assert r.metadata == {"k": 1}


def test_embedder_contrato() -> None:
    emb: Embedder = FakeEmbedder()
    assert emb.embed(["a", "b"]) == [[0.1] * 3, [0.1] * 3]
    assert emb.embed_query("q") == [0.1] * 3
    assert emb.vector_size == 3
    assert emb.max_input_tokens == 512
    assert emb.available is True
    assert emb.check_available() is True


def test_vector_store_contrato() -> None:
    store: VectorStore = FakeStore()
    assert store.count() == 0
    assert store.available is True
    assert store.check_available() is True
    assert store.upsert([VectorItem("a1", [0.1], "p")]) == 1
    assert store.upsert([VectorItem("a2", [0.2], "p")]) == 1
    assert store.count() == 2
    ids, next_off = store.list_ids(limit=1, offset=None)
    assert ids == ["a1"]
    assert next_off is None
    res = store.search([0.1], top_k=1)
    assert res[0].asset_id == "a1"
    assert store.delete(["a1"]) == 1
    assert store.count() == 1
    assert store.delete(["no-existe"]) == 0
