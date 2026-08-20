"""Cobertura 100x100 de vector_ollama/qdrant/retriever + change_guardian. TASK-20260820-014."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import core.change_guardian as cg
import knowledge.engine.vector_ollama as vo
from core.change_guardian import ChangeGuardian, get_failure_patterns, get_failure_summary, validate_and_clean
from knowledge.engine.vector_base import VectorItem, VectorResult
from knowledge.engine.vector_ollama import OllamaEmbedder, _LRUCache
from knowledge.engine.vector_qdrant import QdrantVectorStore, _point_id
from knowledge.engine.vector_retriever import VectorAugmentedRetriever

# ── vector_ollama: LRU cache ─────────────────────────────────


def test_lru_cache_get_put() -> None:
    c = _LRUCache(ttl=300, maxsize=2)
    assert c.get("k1") is None
    c.put("k1", [1.0])
    c.put("k2", [2.0])
    c.put("k3", [3.0])  # expulsa k1 (LRU)
    assert c.get("k3") == [3.0]
    assert c.get("k1") is None
    assert c.size == 2


def test_lru_cache_ttl_expirado(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _LRUCache(ttl=1, maxsize=10)
    c.put("k1", [1.0])
    monkeypatch.setattr(vo.time, "monotonic", lambda: 1000.0)
    c._cache["k1"] = (0.0, [1.0])  # timestamp viejo
    assert c.get("k1") is None
    assert c.size == 0


def test_lru_cache_move_to_end() -> None:
    c = _LRUCache(ttl=300, maxsize=2)
    c.put("a", [1.0])
    c.put("b", [2.0])
    c.get("a")  # mueve a al final
    c.put("c", [3.0])  # expulsa b
    assert c.get("b") is None
    assert c.get("a") == [1.0]


def test_lru_cache_clear() -> None:
    c = _LRUCache()
    c.put("a", [1.0])
    c.clear()
    assert c.size == 0


# ── vector_ollama: embedder ──────────────────────────────────


def test_ollama_embed_sin_textos() -> None:
    e = OllamaEmbedder()
    assert e.embed([]) == []


def test_ollama_embed_sin_disponible() -> None:
    e = OllamaEmbedder()
    e._degraded = True
    assert e.embed(["x"]) == []
    assert e.embed_query("x") == []


def test_ollama_embed_single_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    e = OllamaEmbedder()
    e._cache.put("texto", [0.1, 0.2])
    assert e.embed(["texto"]) == [[0.1, 0.2]]


def test_ollama_embed_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    e = OllamaEmbedder()
    monkeypatch.setattr(vo, "_embed", lambda texts, model: [[0.1, 0.2], [0.3, 0.4]])
    res = e.embed(["a", "b"])
    assert len(res) == 2
    assert e.vector_size == 2
    assert e._cache.size == 2
    # segundo embed: vector_size ya seteado → rama else
    res2 = e.embed(["c", "d"])
    assert len(res2) == 2
    assert e.vector_size == 2


def test_ollama_embed_vacio_devuelto(monkeypatch: pytest.MonkeyPatch) -> None:
    e = OllamaEmbedder()
    monkeypatch.setattr(vo, "_embed", lambda texts, model: [])
    assert e.embed(["a"]) == []


def test_ollama_embed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    e = OllamaEmbedder()

    def _roto(texts, model):
        msg = "ollama caido"
        raise RuntimeError(msg)

    monkeypatch.setattr(vo, "_embed", _roto)
    assert e.embed(["a"]) == []
    assert e._degraded is True
    assert e.available is False


def test_ollama_embed_query_vacio() -> None:
    e = OllamaEmbedder()
    assert e.embed_query("") == []


def test_ollama_embed_query_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    e = OllamaEmbedder()
    monkeypatch.setattr(vo, "_embed", lambda texts, model: [[0.5]])
    assert e.embed_query("q") == [0.5]


def test_ollama_props() -> None:
    e = OllamaEmbedder()
    assert e.vector_size == 0
    assert e.max_input_tokens == 0
    assert e.available is True
    e.close()  # no lanza


def test_ollama_check_available_sano() -> None:
    e = OllamaEmbedder()
    assert e.check_available() is True  # no degradado → True directo


def test_ollama_check_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    e = OllamaEmbedder()
    e._degraded = True
    e._last_check = time.monotonic()
    assert e.check_available() is False  # backoff activo


def test_ollama_check_health_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    e = OllamaEmbedder()
    e._degraded = True
    e._last_check = 0.0
    monkeypatch.setattr(vo, "_health", lambda: {"status": "ok"})
    assert e.check_available() is True
    assert e._degraded is False
    assert e._backoff == 1.0


def test_ollama_check_health_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    e = OllamaEmbedder()
    e._degraded = True
    e._last_check = 0.0
    monkeypatch.setattr(vo, "_health", lambda: {"status": "error"})
    assert e.check_available() is False
    assert e._backoff == 2.0


def test_ollama_check_health_excepcion(monkeypatch: pytest.MonkeyPatch) -> None:
    e = OllamaEmbedder()
    e._degraded = True
    e._last_check = 0.0

    def _roto():
        msg = "no health"
        raise RuntimeError(msg)

    monkeypatch.setattr(vo, "_health", _roto)
    assert e.check_available() is False
    assert e._backoff == 2.0


# ── vector_qdrant ────────────────────────────────────────────


def test_point_id_unico() -> None:
    assert _point_id() != _point_id()
    assert len(_point_id()) == 16


class _FakeResp:
    def __init__(self, status_code: int = 200, data: dict | None = None) -> None:
        self.status_code = status_code
        self._data = data or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("err", request=None, response=self)  # type: ignore[arg-type]

    def json(self) -> dict:
        return self._data


class _FakeClient:
    def __init__(self, respuestas: list | None = None) -> None:
        self.respuestas = list(respuestas or [])
        self.calls: list[tuple[str, str, dict | None]] = []
        self.raise_error: Exception | None = None

    def post(self, url: str, json: dict | None = None, timeout: float | None = None) -> _FakeResp:
        self.calls.append(("post", url, json))
        if self.raise_error:
            raise self.raise_error
        return self.respuestas.pop(0) if self.respuestas else _FakeResp()

    def put(self, url: str, json: dict | None = None) -> _FakeResp:
        self.calls.append(("put", url, json))
        if self.raise_error:
            raise self.raise_error
        return self.respuestas.pop(0) if self.respuestas else _FakeResp()

    def get(self, url: str) -> _FakeResp:
        self.calls.append(("get", url, None))
        if self.raise_error:
            raise self.raise_error
        return self.respuestas.pop(0) if self.respuestas else _FakeResp()

    def close(self) -> None:
        pass


def _store(client: _FakeClient | None = None) -> QdrantVectorStore:
    s = QdrantVectorStore(host="fake", port=1)
    s._client = client or _FakeClient()  # type: ignore[assignment]
    return s


def test_qdrant_search_ok() -> None:
    fc = _FakeClient([_FakeResp(200, {"result": [{"id": "a1", "score": 0.9, "payload": {"x": 1}}]})])
    s = _store(fc)
    res = s.search([0.1, 0.2])
    assert len(res) == 1
    assert res[0].asset_id == "a1"
    assert res[0].score == 0.9
    assert res[0].metadata == {"x": 1}


def test_qdrant_search_con_filter() -> None:
    fc = _FakeClient([_FakeResp(200, {"result": []})])
    s = _store(fc)
    s.search([0.1], filter={"asset_type": "pdf"})
    assert "filter" in fc.calls[0][2]
    assert fc.calls[0][2]["filter"] == {"must": [{"key": "asset_type", "match": {"value": "pdf"}}]}


def test_qdrant_search_degradado() -> None:
    s = _store()
    s._degraded = True
    assert s.search([0.1]) == []


def test_qdrant_search_sin_vector() -> None:
    s = _store()
    assert s.search([]) == []


def test_qdrant_search_error() -> None:
    import httpx

    fc = _FakeClient()
    fc.raise_error = httpx.ConnectError("sin conexion")
    s = _store(fc)
    assert s.search([0.1]) == []
    assert s._degraded is True


def test_qdrant_upsert_ok() -> None:
    fc = _FakeClient([_FakeResp(200, {}), _FakeResp(200, {})])  # ensure_collection + put
    s = _store(fc)
    n = s.upsert([VectorItem(asset_id="a1", vector=[0.1], text_preview="t")])
    assert n == 1
    assert fc.calls[0][0] == "put"  # ensure collection


def test_qdrant_upsert_vacio() -> None:
    s = _store()
    assert s.upsert([]) == 0


def test_qdrant_upsert_degradado() -> None:
    s = _store()
    s._degraded = True
    assert s.upsert([VectorItem(asset_id="a", vector=[0.1], text_preview="")]) == 0


def test_qdrant_upsert_error() -> None:
    import httpx

    fc = _FakeClient()
    fc.raise_error = httpx.ConnectError("no")
    s = _store(fc)
    assert s.upsert([VectorItem(asset_id="a", vector=[0.1], text_preview="")]) == 0
    assert s._degraded is True


def test_qdrant_delete_ok() -> None:
    fc = _FakeClient([_FakeResp(200, {})])
    s = _store(fc)
    assert s.delete(["a1", "a2"]) == 2


def test_qdrant_delete_vacio() -> None:
    s = _store()
    assert s.delete([]) == 0


def test_qdrant_delete_degradado() -> None:
    s = _store()
    s._degraded = True
    assert s.delete(["a"]) == 0


def test_qdrant_count_degradado() -> None:
    s = _store()
    s._degraded = True
    assert s.count() == 0


def test_qdrant_ensure_collection_status_error() -> None:
    import httpx

    fc = _FakeClient([_FakeResp(500, {})])
    s = _store(fc)
    with pytest.raises(httpx.HTTPError):
        s._ensure_collection([0.1])


def test_qdrant_delete_error() -> None:
    import httpx

    fc = _FakeClient()
    fc.raise_error = httpx.ConnectError("no")
    s = _store(fc)
    assert s.delete(["a"]) == 0
    assert s._degraded is True


def test_qdrant_count_ok() -> None:
    fc = _FakeClient([_FakeResp(200, {"result": {"count": 7}})])
    s = _store(fc)
    assert s.count() == 7


def test_qdrant_count_error() -> None:
    import httpx

    fc = _FakeClient()
    fc.raise_error = httpx.ConnectError("no")
    s = _store(fc)
    assert s.count() == 0


def test_qdrant_list_ids_ok() -> None:
    fc = _FakeClient([_FakeResp(200, {"result": {"points": [{"id": "a1"}, {"id": "a2"}], "next_page_offset": "xyz"}})])
    s = _store(fc)
    ids, nxt = s.list_ids()
    assert ids == ["a1", "a2"]
    assert nxt == "xyz"


def test_qdrant_list_ids_con_offset() -> None:
    fc = _FakeClient([_FakeResp(200, {"result": {"points": [], "next_page_offset": None}})])
    s = _store(fc)
    ids, nxt = s.list_ids(offset="abc")
    assert fc.calls[0][2]["offset"] == "abc"
    assert nxt is None


def test_qdrant_list_ids_degradado() -> None:
    s = _store()
    s._degraded = True
    assert s.list_ids() == ([], None)


def test_qdrant_list_ids_error() -> None:
    import httpx

    fc = _FakeClient()
    fc.raise_error = httpx.ConnectError("no")
    s = _store(fc)
    assert s.list_ids() == ([], None)


def test_qdrant_check_available_sano() -> None:
    s = _store()
    assert s.check_available() is True


def test_qdrant_check_backoff() -> None:
    s = _store()
    s._degraded = True
    s._last_check = time.monotonic()
    assert s.check_available() is False


def test_qdrant_check_health_ok() -> None:
    fc = _FakeClient([_FakeResp(200, {})])
    s = _store(fc)
    s._degraded = True
    s._last_check = 0.0
    assert s.check_available() is True
    assert s._degraded is False


def test_qdrant_check_health_no_200() -> None:
    fc = _FakeClient([_FakeResp(500, {})])
    s = _store(fc)
    s._degraded = True
    s._last_check = 0.0
    assert s.check_available() is False
    assert s._degraded is True
    assert s._backoff == 2.0


def test_qdrant_check_health_error() -> None:
    import httpx

    fc = _FakeClient()
    fc.raise_error = httpx.ConnectError("no")
    s = _store(fc)
    s._degraded = True
    s._last_check = 0.0
    assert s.check_available() is False


def test_qdrant_ensure_collection_409() -> None:
    fc = _FakeClient([_FakeResp(409, {})])
    s = _store(fc)
    s._ensure_collection([0.1, 0.2])
    assert fc.calls[0][2]["vectors"]["size"] == 2
    assert fc.calls[0][2]["vectors"]["distance"] == "Cosine"


def test_qdrant_ensure_collection_error() -> None:
    import httpx

    fc = _FakeClient()
    fc.raise_error = httpx.ConnectError("no")
    s = _store(fc)
    with pytest.raises(httpx.HTTPError):
        s._ensure_collection([0.1])


def test_qdrant_translate_filter() -> None:
    assert QdrantVectorStore._translate_filter({"a": 1, "b": "x"}) == {
        "must": [{"key": "a", "match": {"value": 1}}, {"key": "b", "match": {"value": "x"}}]
    }


def test_qdrant_close() -> None:
    fc = _FakeClient()
    s = _store(fc)
    s.close()  # no lanza


# ── vector_retriever ─────────────────────────────────────────


class _GraphFake:
    def __init__(self, results: list | None = None) -> None:
        self.results = results or []

    def retrieve_assets(self, query: str, limit: int = 10, asset_type=None) -> list:
        return self.results


class _StoreFake:
    def __init__(self, assets: dict | None = None) -> None:
        self._assets = assets or {}
        self.lists: list[tuple] = []

    def get_asset(self, aid: str):
        return self._assets.get(aid)

    def list_assets(self, limit: int = 100, offset: int = 0):
        self.lists.append((limit, offset))
        ids = sorted(self._assets.keys())
        page = ids[offset : offset + limit]
        return [self._assets[i] for i in page]


class _EmbedderFake:
    def __init__(self, vecs: list | None = None, available: bool = True, error: bool = False) -> None:
        self._vecs = [[0.1, 0.2]] if vecs is None else vecs
        self.available = available
        self._error = error
        self.calls = []

    def embed_query(self, text: str) -> list[float]:
        self.calls.append(("query", text))
        if self._error:
            msg = "embed fallo"
            raise RuntimeError(msg)
        return self._vecs[0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(("embed", texts))
        if self._error:
            msg = "embed fallo"
            raise RuntimeError(msg)
        if not self._vecs:
            return []
        return [self._vecs[0] for _ in texts]


class _VectorStoreFake:
    def __init__(self, available: bool = True, search_results: list | None = None) -> None:
        self.available = available
        self._search = search_results or []
        self.calls = []
        self.deleted = 0
        self.upserted = 0

    def search(self, query_vec: list[float], top_k: int = 10) -> list:
        self.calls.append(("search", query_vec, top_k))
        return self._search

    def list_ids(self, limit: int = 100, offset: str | None = None):
        self.calls.append(("list", limit, offset))
        if offset is None:
            return ["v1", "v2"], "next"
        return ["v3"], None

    def delete(self, asset_ids: list[str]) -> int:
        self.calls.append(("delete", asset_ids))
        n = len(asset_ids)
        self.deleted += n
        return n

    def upsert(self, items: list[VectorItem]) -> int:
        self.calls.append(("upsert", items))
        self.upserted = len(items)
        return len(items)


def _asset(aid: str) -> object:
    return type("A", (), {"asset_id": aid, "metadata": {"title": f"t-{aid}", "text_preview": f"p-{aid}"}})()


def _res(aid: str) -> object:
    return type("R", (), {"asset_id": aid})()


def test_retriever_heuristica_sola() -> None:
    g = _GraphFake([_res("h1"), _res("h2")])
    store = _StoreFake({"h1": _asset("h1")})
    r = VectorAugmentedRetriever(g, store)
    res = r.retrieve_assets("q", use_vector=False)
    assert res == [store._assets["h1"]]


def test_retriever_sin_vector_available() -> None:
    g = _GraphFake([_res("h1")])
    store = _StoreFake({"h1": _asset("h1")})
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(available=False), vector_store=_VectorStoreFake())
    res = r.retrieve_assets("q", use_vector=True)
    assert len(res) == 1


def test_retriever_vector_fusion() -> None:
    g = _GraphFake([_res("a"), _res("b")])
    store = _StoreFake({"a": _asset("a"), "b": _asset("b"), "c": _asset("c")})
    vs = _VectorStoreFake(search_results=[VectorResult(asset_id="c", score=0.9)])
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=vs)
    res = r.retrieve_assets("q", use_vector=True)
    # RRF: a=1/61, b=1/62, c=1/61 → a y c empatados, luego b
    assert len(res) >= 2


def test_retriever_rrf_mismo_asset_en_ambos() -> None:
    g = _GraphFake([_res("a")])
    store = _StoreFake({"a": _asset("a")})
    vs = _VectorStoreFake(search_results=[VectorResult(asset_id="a", score=0.9)])
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=vs)
    res = r.retrieve_assets("q", use_vector=True)
    assert res == [store._assets["a"]]  # score sumado: a domina


def test_retriever_vector_sin_resultados() -> None:
    g = _GraphFake([_res("h1")])
    store = _StoreFake({"h1": _asset("h1")})
    vs = _VectorStoreFake(search_results=[])
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=vs)
    res = r.retrieve_assets("q", use_vector=True)
    assert len(res) == 1


def test_retriever_vector_error() -> None:
    g = _GraphFake([_res("h1")])
    store = _StoreFake({"h1": _asset("h1")})
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(error=True), vector_store=_VectorStoreFake())
    res = r.retrieve_assets("q", use_vector=True)
    assert len(res) == 1  # degradación graceful


def test_retriever_vector_query_vec_vacio() -> None:
    g = _GraphFake([_res("h1")])
    store = _StoreFake({"h1": _asset("h1")})

    class _EmbedVacio:
        available = True

        def embed_query(self, text: str) -> list[float]:
            return []  # sin vector → no busca en vector store

        def embed(self, texts: list[str]) -> list[list[float]]:
            return []

    vs = _VectorStoreFake()
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedVacio(), vector_store=vs)  # type: ignore[arg-type]
    res = r.retrieve_assets("q", use_vector=True)
    assert len(res) == 1
    assert not any(c[0] == "search" for c in vs.calls)


def test_retriever_vector_result_sin_asset_id() -> None:
    g = _GraphFake([_res("h1")])
    store = _StoreFake({"h1": _asset("h1")})
    vs = _VectorStoreFake(search_results=[type("SinId", (), {})()])  # sin atributo asset_id
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=vs)
    res = r.retrieve_assets("q", use_vector=True)
    assert len(res) == 1  # el vector sin id se ignora


def test_retriever_use_vector_sin_embedder() -> None:
    g = _GraphFake([_res("h1")])
    store = _StoreFake({"h1": _asset("h1")})
    r = VectorAugmentedRetriever(g, store, embedder=None, vector_store=_VectorStoreFake())
    res = r.retrieve_assets("q", use_vector=True)
    assert len(res) == 1  # no disponible → solo heurística


def test_retriever_use_vector_sin_store_pero_con_embedder() -> None:
    g = _GraphFake([_res("h1")])
    store = _StoreFake({"h1": _asset("h1")})
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=None)
    res = r.retrieve_assets("q", use_vector=True)
    assert len(res) == 1  # _vector_available False → solo heurística


def test_retriever_upsert_resto_unico_asset() -> None:
    g = _GraphFake()
    store = _StoreFake({"solo": _asset("solo")})
    vs = _VectorStoreFake()
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=vs)
    stats = r.reconcile(dry_run=False, batch_size=100)  # 1 asset < batch → rama final
    assert stats["upserted"] == 1


def test_retriever_upsert_batch_exacto() -> None:
    g = _GraphFake()
    store = _StoreFake({f"a{i}": _asset(f"a{i}") for i in range(4)})
    vs = _VectorStoreFake()
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=vs)
    stats = r.reconcile(dry_run=False, batch_size=2)  # 4 assets = 2 batches exactos
    assert stats["upserted"] == 4


def test_retriever_eliminar_huerfanos_sin_store() -> None:
    g = _GraphFake()
    r = VectorAugmentedRetriever(g, _StoreFake(), embedder=_EmbedderFake(), vector_store=None)
    r._eliminar_huerfanos({"x"}, 10, {"deleted": 0})  # store None → return


def test_retriever_get_vector_ids_sin_store() -> None:
    g = _GraphFake()
    r = VectorAugmentedRetriever(g, _StoreFake())
    assert r._get_vector_ids() == set()


def test_retriever_upsert_batch_sin_backend() -> None:
    g = _GraphFake()
    r = VectorAugmentedRetriever(g, _StoreFake(), embedder=None, vector_store=None)
    r._upsert_batch([_asset("a")], ["t"], {"upserted": 0})  # no lanza


def test_retriever_upsert_batch_items_vacios() -> None:
    g = _GraphFake()
    store = _StoreFake({"a1": _asset("a1")})

    class _EmbedVacios:
        available = True

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.0], [0.0]]  # 2 vectores

        def embed_query(self, text: str) -> list[float]:
            return [0.1]

    class _VSCuenta:
        available = True

        def search(self, query_vec, top_k: int = 10):
            return []

        def list_ids(self, limit: int = 100, offset: str | None = None):
            return [], None

        def delete(self, asset_ids: list[str]) -> int:
            return 0

        def upsert(self, items: list[VectorItem]) -> int:
            return len(items)

    r = VectorAugmentedRetriever(g, store, embedder=_EmbedVacios(), vector_store=_VSCuenta())  # type: ignore[arg-type]
    stats = r.reconcile(dry_run=False)
    # 1 asset, 2 vectores → zip corta en 1 item
    assert stats["upserted"] == 1


def test_retriever_rrf_sin_asset_id() -> None:
    g = _GraphFake([type("SinId", (), {})()])  # sin asset_id
    store = _StoreFake()
    r = VectorAugmentedRetriever(g, store)
    assert r.retrieve_assets("q") == []


def test_retriever_reconcile_sin_backend() -> None:
    g = _GraphFake()
    r = VectorAugmentedRetriever(g, _StoreFake())
    assert r.reconcile() == {"to_upsert": 0, "to_delete": 0, "upserted": 0, "deleted": 0}


def test_retriever_reconcile_dry_run() -> None:
    g = _GraphFake()
    store = _StoreFake({"a1": _asset("a1"), "a2": _asset("a2")})
    vs = _VectorStoreFake()
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=vs)
    stats = r.reconcile(dry_run=True)
    assert stats["to_upsert"] == 2
    assert stats["to_delete"] == 3  # v1,v2,v3 no están en assets
    assert stats["upserted"] == 0


def test_retriever_reconcile_real() -> None:
    g = _GraphFake()
    store = _StoreFake({"a1": _asset("a1")})
    vs = _VectorStoreFake()
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=vs)
    stats = r.reconcile(dry_run=False)
    assert stats["to_upsert"] == 1
    assert stats["upserted"] == 1
    assert stats["deleted"] >= 1


def test_retriever_list_assets_error() -> None:
    g = _GraphFake()

    class _StoreRoto:
        def list_assets(self, limit: int = 100, offset: int = 0):
            msg = "store roto"
            raise RuntimeError(msg)

    vs = _VectorStoreFake()
    r = VectorAugmentedRetriever(g, _StoreRoto(), embedder=_EmbedderFake(), vector_store=vs)  # type: ignore[arg-type]
    stats = r.reconcile()
    assert stats["to_upsert"] == 0


def test_retriever_upsert_embed_error() -> None:
    g = _GraphFake()
    store = _StoreFake({"a1": _asset("a1")})
    vs = _VectorStoreFake()
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(error=True), vector_store=vs)
    stats = r.reconcile(dry_run=False)
    assert stats["upserted"] == 0


def test_retriever_upsert_embed_vacio() -> None:
    g = _GraphFake()
    store = _StoreFake({"a1": _asset("a1")})
    vs = _VectorStoreFake()
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(vecs=[]), vector_store=vs)
    stats = r.reconcile(dry_run=False)
    assert stats["upserted"] == 0


def test_retriever_get_vector_ids_error() -> None:
    g = _GraphFake()
    store = _StoreFake()

    class _VSRoto:
        available = True

        def list_ids(self, limit: int = 100, offset: str | None = None):
            msg = "qdrant caido"
            raise RuntimeError(msg)

    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=_VSRoto())  # type: ignore[arg-type]
    assert r._get_vector_ids() == set()


def test_retriever_get_vector_ids_loop_offset() -> None:
    g = _GraphFake()

    class _VSLoop:
        available = True

        def list_ids(self, limit: int = 100, offset: str | None = None):
            return ["x"], "mismo-offset"

    r = VectorAugmentedRetriever(g, _StoreFake(), embedder=_EmbedderFake(), vector_store=_VSLoop())  # type: ignore[arg-type]
    ids = r._get_vector_ids()
    assert ids == {"x"}


def test_retriever_get_vector_ids_sin_batch() -> None:
    g = _GraphFake()

    class _VSVacio:
        available = True

        def list_ids(self, limit: int = 100, offset: str | None = None):
            return [], None

    r = VectorAugmentedRetriever(g, _StoreFake(), embedder=_EmbedderFake(), vector_store=_VSVacio())  # type: ignore[arg-type]
    assert r._get_vector_ids() == set()


def test_retriever_upsert_batch_multiple() -> None:
    g = _GraphFake()
    store = _StoreFake({"a1": _asset("a1"), "a2": _asset("a2"), "a3": _asset("a3")})
    vs = _VectorStoreFake()
    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderFake(), vector_store=vs)
    stats = r.reconcile(dry_run=False, batch_size=2)
    assert stats["upserted"] == 3  # batch de 2 + resto


def test_retriever_upsert_batch_embed_vacio_parcial() -> None:
    g = _GraphFake()
    store = _StoreFake({"a1": _asset("a1")})

    class _EmbedderParcial:
        available = True

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2], []]

        def embed_query(self, text: str) -> list[float]:
            return [0.1]

    class _VSParcial:
        available = True

        def search(self, query_vec, top_k: int = 10):
            return []

        def list_ids(self, limit: int = 100, offset: str | None = None):
            return [], None

        def delete(self, asset_ids: list[str]) -> int:
            return 0

        def upsert(self, items: list[VectorItem]) -> int:
            return len(items)

    r = VectorAugmentedRetriever(g, store, embedder=_EmbedderParcial(), vector_store=_VSParcial())  # type: ignore[arg-type]
    stats = r.reconcile(dry_run=False)
    # embed devuelve [[0.1,0.2], []] → item vacío filtrado por `if v`
    assert stats["upserted"] == 1


# ── change_guardian ──────────────────────────────────────────


def test_git_comando(monkeypatch: pytest.MonkeyPatch) -> None:
    class _R:
        returncode = 0
        stdout = "salida"
        stderr = ""

    monkeypatch.setattr(cg.subprocess, "run", lambda *a, **k: _R())
    ok, out = cg._git("status")
    assert ok is True
    assert out == "salida"


def test_get_modified_tracked_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cg, "_git", lambda *a: (True, "a.py\nb.py\n"))
    assert cg._get_modified_tracked_files() == ["a.py", "b.py"]


def test_load_patterns_ok(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    f = Path(str(tmp_path)) / "failure_patterns.json"
    f.write_text(json.dumps([{"tipo": "x"}]))
    monkeypatch.setattr(cg, "PATTERNS_FILE", f)
    assert cg._load_patterns() == [{"tipo": "x"}]


def test_load_patterns_corrupto(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    f = Path(str(tmp_path)) / "failure_patterns.json"
    f.write_text("{corrupto")
    monkeypatch.setattr(cg, "PATTERNS_FILE", f)
    assert cg._load_patterns() == []


def test_load_patterns_no_existe(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cg, "PATTERNS_FILE", Path(str(tmp_path)) / "no.json")
    assert cg._load_patterns() == []


def test_save_pattern(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    f = Path(str(tmp_path)) / "failure_patterns.json"
    monkeypatch.setattr(cg, "PATTERNS_FILE", f)
    cg._save_pattern("tipo", ["a.py"], "error", "diff")
    data = json.loads(f.read_text())
    assert len(data) == 1
    assert data[0]["tipo_cambio"] == "tipo"
    assert data[0]["error"] == "error"


def test_change_guardian_context_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    g = ChangeGuardian("test")
    monkeypatch.setattr(g, "_run_tests", lambda: (True, "ok"))
    with g:
        pass  # tests pasan, no rollback


def test_change_guardian_excepcion(monkeypatch: pytest.MonkeyPatch) -> None:
    g = ChangeGuardian("test")
    monkeypatch.setattr(g, "_rollback", lambda reason: None)
    with pytest.raises(ValueError), g:
        msg = "boom"
        raise ValueError(msg)


def test_change_guardian_tests_fallan(monkeypatch: pytest.MonkeyPatch) -> None:
    g = ChangeGuardian("test")
    monkeypatch.setattr(g, "_run_tests", lambda: (False, "falló"))
    monkeypatch.setattr(g, "_rollback", lambda reason: None)
    with g:
        pass


def test_run_tests_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class _R:
        returncode = 0
        stdout = "3 passed"
        stderr = ""

    monkeypatch.setattr(cg.subprocess, "run", lambda *a, **k: _R())
    g = ChangeGuardian("x")
    passed, error = g._run_tests()
    assert passed is True
    assert "3 passed" in error


def test_run_tests_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _timeout(*a, **k):
        raise __import__("subprocess").TimeoutExpired("pytest", 360)

    monkeypatch.setattr(cg.subprocess, "run", _timeout)
    g = ChangeGuardian("x")
    passed, error = g._run_tests()
    assert passed is False
    assert "superaron" in error


def test_run_tests_excepcion(monkeypatch: pytest.MonkeyPatch) -> None:
    def _roto(*a, **k):
        msg = "no pytest"
        raise OSError(msg)

    monkeypatch.setattr(cg.subprocess, "run", _roto)
    g = ChangeGuardian("x")
    passed, error = g._run_tests()
    assert passed is False
    assert "no pytest" in error


def test_rollback_con_cambios(monkeypatch: pytest.MonkeyPatch) -> None:
    g = ChangeGuardian("test")
    llamadas: list = []
    monkeypatch.setattr(cg, "_git", lambda *a: llamadas.append(a) or (True, "diff"))
    monkeypatch.setattr(cg, "_get_modified_tracked_files", lambda: ["a.py", "b.py"])
    monkeypatch.setattr(cg, "_save_pattern", lambda *a, **k: None)
    g._rollback("razón")
    assert any(a[0] == "checkout" for a in llamadas)


def test_rollback_sin_cambios(monkeypatch: pytest.MonkeyPatch) -> None:
    g = ChangeGuardian("test")
    llamadas: list = []
    monkeypatch.setattr(cg, "_git", lambda *a: llamadas.append(a) or (True, ""))
    monkeypatch.setattr(cg, "_get_modified_tracked_files", lambda: [])
    monkeypatch.setattr(cg, "_save_pattern", lambda *a, **k: None)
    g._rollback("razón")


def test_validate_and_clean_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    g = ChangeGuardian("x")
    monkeypatch.setattr(cg, "ChangeGuardian", lambda *a, **k: g)
    monkeypatch.setattr(g, "_run_tests", lambda: (True, "ok"))
    assert validate_and_clean() is True


def test_validate_and_clean_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    g = ChangeGuardian("x")
    monkeypatch.setattr(cg, "ChangeGuardian", lambda *a, **k: g)
    monkeypatch.setattr(g, "_run_tests", lambda: (False, "falló"))
    monkeypatch.setattr(cg, "_git", lambda *a: (True, ""))
    monkeypatch.setattr(cg, "_get_modified_tracked_files", lambda: [])
    monkeypatch.setattr(cg, "_save_pattern", lambda *a, **k: None)
    assert validate_and_clean() is False


def test_validate_and_clean_falla_con_modificados(monkeypatch: pytest.MonkeyPatch) -> None:
    g = ChangeGuardian("x")
    monkeypatch.setattr(cg, "ChangeGuardian", lambda *a, **k: g)
    monkeypatch.setattr(g, "_run_tests", lambda: (False, "falló"))
    llamadas: list = []
    monkeypatch.setattr(cg, "_git", lambda *a: llamadas.append(a) or (True, ""))
    monkeypatch.setattr(cg, "_get_modified_tracked_files", lambda: ["a.py"])
    monkeypatch.setattr(cg, "_save_pattern", lambda *a, **k: None)
    assert validate_and_clean() is False
    assert any(a[0] == "checkout" for a in llamadas)


def test_get_failure_patterns() -> None:
    assert isinstance(get_failure_patterns(), list)


def test_get_failure_summary_vacio(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cg, "PATTERNS_FILE", Path(str(tmp_path)) / "no.json")
    assert get_failure_summary() == "Sin fallos registrados"


def test_get_failure_summary_con_datos(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    f = Path(str(tmp_path)) / "failure_patterns.json"
    f.write_text(json.dumps([{"fecha": "2026-08-20T10:00:00", "tipo_cambio": "fix", "error": "error corto"}]))
    monkeypatch.setattr(cg, "PATTERNS_FILE", f)
    summary = get_failure_summary()
    assert "fix" in summary
    assert "2026-08-20" in summary
