"""Cobertura 100x100 de motor/core/qdrant_client.py (TASK-20260814-003).

Cubre QdrantClient (nativo + REST fallback) y URAQdrantClient (async) con
mocks de qdrant_client.QdrantClient y httpx, sin conexión real.
"""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import httpx

import motor.core.qdrant_client as qc_mod
from motor.core.qdrant_client import (
    COLECCION_DOCUMENTOS,
    COLECCION_INCIDENTES,
    COLECCION_TRANSACCIONES,
    VECTOR_SIZE,
    VECTOR_SIZE_EMBEDDING,
    QdrantClient,
    URAQdrantClient,
    generar_sparse_vector,
)

if TYPE_CHECKING:
    import pytest


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        qdrant_host="127.0.0.1",
        qdrant_port=6333,
        schema_version="3.1",
    )


# ── sparse vector ────────────────────────────────────────────────────────────


class TestSparseVector:
    def test_normal(self) -> None:
        out = generar_sparse_vector("Hola mundo hola")
        assert out["indices"]
        assert len(out["indices"]) == len(out["values"])
        assert len(out["indices"]) == 2  # hola, mundo

    def test_max_tokens(self) -> None:
        out = generar_sparse_vector(" ".join(f"w{i}" for i in range(20)), max_tokens=5)
        assert len(out["indices"]) <= 5

    def test_vacio(self) -> None:
        out = generar_sparse_vector("")
        assert out == {"indices": [], "values": []}


# ── fakes nativos ────────────────────────────────────────────────────────────


class FakeNativeClient:
    """Simula qdrant_client.QdrantClient nativo."""

    def __init__(self, *, collections_ok: bool = True, colecciones_existentes: set[str] | None = None) -> None:
        self.host = ""
        self.port = 0
        self.timeout = 0
        self._collections_ok = collections_ok
        self._existentes = set(colecciones_existentes or set())
        self.upserted: list[tuple[str, list[Any]]] = []
        self.deleted: list[tuple[str, Any]] = []
        self.points: list[SimpleNamespace] = []
        self.scroll_calls = 0
        self.health_ok = True
        self.recreate_kwargs: list[dict[str, Any]] = []

    def get_collections(self) -> None:
        if not self._collections_ok:
            raise RuntimeError("no collections")

    def get_collection(self, name: str) -> None:
        if name not in self._existentes:
            raise _UnexpectedResponse("404")

    def recreate_collection(self, **kw: Any) -> None:
        self._existentes.add(kw.get("collection_name", ""))
        self.recreate_kwargs.append(kw)

    def upsert(self, collection_name: str, points: list[Any]) -> None:
        self.upserted.append((collection_name, points))

    def delete(self, collection_name: str, points_selector: Any) -> None:
        self.deleted.append((collection_name, points_selector))

    def query_points(self, collection_name: str, query: Any, limit: int) -> SimpleNamespace:
        return SimpleNamespace(points=self.points)

    def scroll(self, collection_name: str, limit: int) -> tuple[list[Any], Any]:
        self.scroll_calls += 1
        return (self.points, None)


class _UnexpectedResponse(Exception):
    pass


class _FakeQdrantModule:
    """Sustituye el paquete qdrant_client en sys.modules."""

    def __init__(self, native: FakeNativeClient) -> None:
        self.native = native
        self.http = SimpleNamespace(
            exceptions=SimpleNamespace(UnexpectedResponse=_UnexpectedResponse),
            models=SimpleNamespace(
                VectorParams=lambda **kw: SimpleNamespace(**kw),
                Distance=SimpleNamespace(COSINE="Cosine"),
                PointStruct=lambda **kw: SimpleNamespace(**kw),
                FilterSelector=lambda **kw: SimpleNamespace(**kw),
                Filter=lambda **kw: SimpleNamespace(**kw),
                FieldCondition=lambda **kw: SimpleNamespace(**kw),
                MatchValue=lambda **kw: SimpleNamespace(**kw),
            ),
        )

    @property
    def QdrantClient(self) -> Any:
        def factory(*args: Any, **kw: Any) -> FakeNativeClient:
            return self.native

        return factory


def _instalar_qdrant_fake(monkeypatch: pytest.MonkeyPatch, native: FakeNativeClient) -> None:
    fake = _FakeQdrantModule(native)
    monkeypatch.setitem(sys.modules, "qdrant_client", fake)  # type: ignore[arg-type]
    monkeypatch.setitem(sys.modules, "qdrant_client.http", fake.http)  # type: ignore[arg-type]
    monkeypatch.setitem(sys.modules, "qdrant_client.http.exceptions", fake.http.exceptions)  # type: ignore[arg-type]
    monkeypatch.setitem(sys.modules, "qdrant_client.http.models", fake.http.models)  # type: ignore[arg-type]


# ── QdrantClient: conexión nativa ────────────────────────────────────────────


class TestConexionNativa:
    def test_conecta_nativo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        c = QdrantClient(_config())
        assert c.disponible is True
        assert c._modo_rest is False
        assert c._cliente is native
        assert c.embedding_semaphore._value == 1

    def test_conecta_nativo_crea_colecciones(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        QdrantClient(_config())
        assert COLECCION_INCIDENTES in native._existentes
        assert COLECCION_DOCUMENTOS in native._existentes
        assert COLECCION_TRANSACCIONES in native._existentes
        recreadas = {kw["collection_name"]: kw for kw in native.recreate_kwargs}
        assert set(recreadas) == {
            COLECCION_INCIDENTES,
            COLECCION_DOCUMENTOS,
            COLECCION_TRANSACCIONES,
        }
        inc = recreadas[COLECCION_INCIDENTES]["vectors_config"]
        assert inc.size == VECTOR_SIZE
        assert inc.distance == "Cosine"
        doc = recreadas[COLECCION_DOCUMENTOS]["vectors_config"]
        assert doc.size == VECTOR_SIZE_EMBEDDING
        assert doc.distance == "Cosine"
        tra = recreadas[COLECCION_TRANSACCIONES]["vectors_config"]
        assert tra.size == VECTOR_SIZE_EMBEDDING
        assert tra.distance == "Cosine"

    def test_nativo_falla_rest_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        llamadas: list[tuple[str, dict | None]] = []

        def fake_get(url: str, timeout: float = 3) -> SimpleNamespace:
            llamadas.append((url, None))
            if url.endswith("/collections") and "points" not in url:
                return SimpleNamespace(status_code=200)
            return SimpleNamespace(status_code=404)

        def fake_put(url: str, **kw: Any) -> SimpleNamespace:
            llamadas.append((url, kw.get("json")))
            return SimpleNamespace(status_code=201)

        monkeypatch.setattr(httpx, "get", fake_get)
        monkeypatch.setattr(httpx, "put", fake_put)
        c = QdrantClient(_config())
        assert c.disponible is True
        assert c._modo_rest is True
        assert c._cliente is None
        assert len(llamadas) >= 4  # check colecciones + puts
        puts = {url: json for url, json in llamadas if json is not None}
        assert len(puts) == 3
        for json_body in puts.values():
            assert json_body["on_disk_payload"] is True
            assert json_body["vectors"]["distance"] == "Cosine"
        inc_url = f"http://{_config().qdrant_host}:{_config().qdrant_port}/collections/{COLECCION_INCIDENTES}"
        doc_url = f"http://{_config().qdrant_host}:{_config().qdrant_port}/collections/{COLECCION_DOCUMENTOS}"
        tra_url = f"http://{_config().qdrant_host}:{_config().qdrant_port}/collections/{COLECCION_TRANSACCIONES}"
        assert puts[inc_url]["vectors"]["size"] == VECTOR_SIZE
        assert puts[doc_url]["vectors"]["size"] == VECTOR_SIZE_EMBEDDING
        assert puts[tra_url]["vectors"]["size"] == VECTOR_SIZE_EMBEDDING

    def test_ambas_fallan(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(
            httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("conn"))
        )
        c = QdrantClient(_config())
        assert c.disponible is False
        assert not hasattr(c, "_modo_rest") or c._modo_rest is False


# ── QdrantClient: guardar documentos ─────────────────────────────────────────


class TestGuardarDocumentos:
    def test_no_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        c = QdrantClient(_config())
        assert c.guardar_documento("d1", "texto") is False
        assert c.guardar_documentos_batch([]) == 0

    def test_nativo_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(qc_mod, "llm_embed", lambda texts, model=None: [[0.1] * VECTOR_SIZE_EMBEDDING for _ in texts])
        c = QdrantClient(_config())
        assert c.guardar_documento("d1", "texto", {"k": "v"}) is True
        assert c.guardar_documentos_batch([("d2", "t2", {})], COLECCION_DOCUMENTOS) == 1
        assert len(native.upserted) == 2

    def test_nativo_sin_cliente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=201))
        monkeypatch.setattr(qc_mod, "llm_embed", lambda texts, model=None: [[0.1] * VECTOR_SIZE_EMBEDDING for _ in texts])
        c = QdrantClient(_config())
        # modo_rest True -> usa REST
        assert c.guardar_documento("d1", "t") is True

    def test_nativo_error_upsert(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(qc_mod, "llm_embed", lambda texts, model=None: [[0.1] * VECTOR_SIZE_EMBEDDING for _ in texts])
        monkeypatch.setattr(
            native, "upsert", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("upsert boom"))
        )
        c = QdrantClient(_config())
        assert c.guardar_documento("d1", "t") is False

    def test_rest_ok_y_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        respuestas: list[Any] = []

        def fake_get(url: str, **kw: Any) -> SimpleNamespace:
            if "/collections" in url and "points" not in url:
                return SimpleNamespace(status_code=200)
            return SimpleNamespace(status_code=404)

        def fake_put(url: str, **kw: Any) -> SimpleNamespace:
            respuestas.append(kw.get("json", {}))
            if "points" in url:
                return SimpleNamespace(status_code=201)
            return SimpleNamespace(status_code=201)

        monkeypatch.setattr(httpx, "get", fake_get)
        monkeypatch.setattr(httpx, "put", fake_put)
        monkeypatch.setattr(qc_mod, "llm_embed", lambda texts, model=None: [[0.1] * VECTOR_SIZE_EMBEDDING for _ in texts])
        c = QdrantClient(_config())
        assert c.guardar_documento("d1", "t") is True
        assert c.guardar_documento("d2", "t") is True

    def test_rest_error_guardar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)

        def fake_get(url: str, **kw: Any) -> SimpleNamespace:
            if "/collections" in url and "points" not in url:
                return SimpleNamespace(status_code=200)
            return SimpleNamespace(status_code=404)

        def fake_put(url: str, **kw: Any) -> SimpleNamespace:
            return SimpleNamespace(status_code=500)

        monkeypatch.setattr(httpx, "get", fake_get)
        monkeypatch.setattr(httpx, "put", fake_put)
        monkeypatch.setattr(qc_mod, "llm_embed", lambda texts, model=None: [[0.1] * VECTOR_SIZE_EMBEDDING for _ in texts])
        c = QdrantClient(_config())
        assert c.guardar_documento("d1", "t") is False


# ── QdrantClient: búsquedas ──────────────────────────────────────────────────


class TestBusquedas:
    def test_buscar_similitud_nativo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        native.points = [
            SimpleNamespace(payload={"texto": "a"}, score=0.9),
            SimpleNamespace(payload={"texto": "b"}, score=0.5),
        ]
        _instalar_qdrant_fake(monkeypatch, native)
        c = QdrantClient(_config())
        out = c.buscar_por_similitud([0.1] * VECTOR_SIZE_EMBEDDING)
        assert len(out) == 2
        assert out[0]["score"] == 0.9

    def test_buscar_similitud_no_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        c = QdrantClient(_config())
        assert c.buscar_por_similitud([0.1]) == []

    def test_buscar_similitud_nativo_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(
            native, "query_points", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("q boom"))
        )
        c = QdrantClient(_config())
        assert c.buscar_por_similitud([0.1]) == []

    def test_buscar_rest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        llamadas: list[str] = []

        def fake_post(url: str, **kw: Any) -> SimpleNamespace:
            llamadas.append(url)
            if "search" in url:
                return SimpleNamespace(
                    status_code=200,
                    json=lambda: {"result": [{"payload": {"p": 1}, "score": 0.7}]},
                )
            return SimpleNamespace(status_code=200, json=lambda: {"result": {"points": []}})

        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=201))
        monkeypatch.setattr(httpx, "post", fake_post)
        c = QdrantClient(_config())
        out = c.buscar_por_similitud([0.1])
        assert len(out) == 1
        assert out[0]["payload"] == {"p": 1}

    def test_buscar_rest_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=201))
        monkeypatch.setattr(
            httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x"))
        )
        c = QdrantClient(_config())
        assert c.buscar_por_similitud([0.1]) == []

    def test_buscar_documentos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        native.points = [SimpleNamespace(payload={"texto": "x"}, score=0.8)]
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(qc_mod, "llm_embed", lambda texts, model=None: [[0.1] * VECTOR_SIZE_EMBEDDING])
        c = QdrantClient(_config())
        out = c.buscar_documentos("consulta")
        assert len(out) == 1


# ── QdrantClient: eliminar, health, incidentes ───────────────────────────────


class TestEliminarHealthIncidentes:
    def test_eliminar_nativo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        c = QdrantClient(_config())
        assert c.eliminar_por_filtro({"source": "x"}) is True
        assert len(native.deleted) == 1

    def test_eliminar_nativo_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(native, "delete", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("d boom")))
        c = QdrantClient(_config())
        assert c.eliminar_por_filtro({"k": "v"}) is False

    def test_eliminar_rest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=201))
        monkeypatch.setattr(
            httpx, "post", lambda *a, **k: SimpleNamespace(status_code=200)
        )
        c = QdrantClient(_config())
        assert c.eliminar_por_filtro({"k": "v"}) is True

    def test_eliminar_rest_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=201))
        monkeypatch.setattr(
            httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x"))
        )
        c = QdrantClient(_config())
        assert c.eliminar_por_filtro({"k": "v"}) is False

    def test_eliminar_no_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        c = QdrantClient(_config())
        assert c.eliminar_por_filtro({"k": "v"}) is False

    def test_health_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        c = QdrantClient(_config())
        assert c.health() is True

    def test_health_no_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        c = QdrantClient(_config())
        assert c.health() is False

    def test_health_rest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=201))
        c = QdrantClient(_config())
        assert c.health() is True

    def test_health_nativo_falla(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        c = QdrantClient(_config())
        monkeypatch.setattr(native, "get_collections", lambda: (_ for _ in ()).throw(RuntimeError("h")))
        assert c.health() is False
        assert c.disponible is False

    def test_guardar_incidente_nativo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        c = QdrantClient(_config())
        incidente = {"ts": "2026-01-01T00:00:00+00:00", "tipo": "oom", "impacto_memoria": [0.5] * VECTOR_SIZE}
        assert c.guardar_incidente(incidente) is True
        assert len(native.upserted) == 1

    def test_guardar_incidente_nativo_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(native, "upsert", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("u")))
        c = QdrantClient(_config())
        assert c.guardar_incidente({"ts": "x"}) is False

    def test_guardar_incidente_no_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        c = QdrantClient(_config())
        assert c.guardar_incidente({"ts": "x"}) is False

    def test_guardar_incidente_rest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        puts: list[dict] = []
        monkeypatch.setattr(httpx, "put", lambda *a, **k: (puts.append(k.get("json")), SimpleNamespace(status_code=201))[1])
        monkeypatch.setattr(httpx, "post", lambda *a, **k: SimpleNamespace(status_code=200))
        c = QdrantClient(_config())
        assert c.guardar_incidente({"ts": "x"}) is True
        assert len(puts) == 1
        point = puts[0]["points"][0]
        assert point["vector"] == [0.0] * VECTOR_SIZE
        assert point["payload"]["timestamp_inicio"] == "x"
        assert point["payload"]["schema_version"] == "3.1"
        assert point["payload"]["origin_node"] == "ASUS"

    def test_guardar_incidente_rest_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        c = QdrantClient(_config())
        assert c.guardar_incidente({"ts": "x"}) is False

    def test_build_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        c = QdrantClient(_config())
        p = c._build_payload({"tipo": "x", "hw_ok": False, "hw_issues": ["a"], "exit_code": 3})
        assert p["tipo_incidencia"] == "x"
        assert p["hw_ok"] is False
        assert p["exit_code"] == 3
        assert p["origin_node"] == "ASUS"
        assert p["segfault"] is False
        assert p["oom_killed"] is False
        assert p["timestamp_resolucion"] == ""
        assert p["subtipo"] == ""
        assert p["resumen"] == ""
        p2 = c._build_payload({})
        assert p2["timestamp_inicio"]  # usa datetime.now

    def test_buscar_incidentes_nativo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        native.points = [SimpleNamespace(payload={"tipo": "oom"})]
        _instalar_qdrant_fake(monkeypatch, native)
        c = QdrantClient(_config())
        out = c.buscar_incidentes(limit=5)
        assert out == [{"tipo": "oom"}]

    def test_buscar_incidentes_no_disponible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        c = QdrantClient(_config())
        assert c.buscar_incidentes() == []

    def test_buscar_incidentes_nativo_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(native, "scroll", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("s")))
        c = QdrantClient(_config())
        assert c.buscar_incidentes() == []

    def test_buscar_incidentes_rest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=201))
        monkeypatch.setattr(
            httpx,
            "post",
            lambda *a, **k: SimpleNamespace(
                status_code=200, json=lambda: {"result": {"points": [{"payload": {"t": 1}}]}}
            ),
        )
        c = QdrantClient(_config())
        assert c.buscar_incidentes() == [{"t": 1}]

    def test_buscar_incidentes_rest_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=201))
        monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        c = QdrantClient(_config())
        assert c.buscar_incidentes() == []

    def test_instancia_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        QdrantClient._instancia = None
        c1 = QdrantClient.instancia(_config())
        c2 = QdrantClient.instancia(_config())
        assert c1 is c2
        assert isinstance(c1, QdrantClient)
        assert c1.config.qdrant_host == "127.0.0.1"
        assert c1.disponible is True
        QdrantClient._instancia = None

    def test_instancia_singleton_concurrencia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Dos threads llaman a la vez: solo se crea una instancia (lock + doble uso)."""
        import threading

        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        QdrantClient._instancia = None
        resultados: list[QdrantClient] = []
        barrier = threading.Barrier(2)

        def worker() -> None:
            barrier.wait()
            resultados.append(QdrantClient.instancia(_config()))

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        assert len(resultados) == 2
        assert resultados[0] is resultados[1]
        assert isinstance(resultados[0], QdrantClient)
        QdrantClient._instancia = None


# ── embeddings ───────────────────────────────────────────────────────────────


class TestEmbeddings:
    def test_generar_embedding_async_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        async def fake_embed_async(texts, model=None):
            return [[0.0] * VECTOR_SIZE_EMBEDDING for _ in texts]

        monkeypatch.setattr(qc_mod, "llm_embed_async", fake_embed_async)
        c = QdrantClient(_config())
        out = asyncio.run(c.generar_embedding_async("t"))
        assert out == [0.0] * VECTOR_SIZE_EMBEDDING

    def test_generar_embedding_async_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        recibidos: list[str] = []

        async def fake_embed_async(texts, model=None):
            recibidos.append(texts)
            return [[0.5] * VECTOR_SIZE_EMBEDDING for _ in texts]

        monkeypatch.setattr(qc_mod, "llm_embed_async", fake_embed_async)
        c = QdrantClient(_config())
        out = asyncio.run(c.generar_embedding_async("t"))
        assert out[0] == 0.5
        assert recibidos == [["t"]]
        assert c.embedding_semaphore._value == 1

    def test_generar_embedding_sync(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        recibidos: list[str] = []

        async def fake_embed_async(texts, model=None):
            recibidos.append(texts)
            return [[0.5] * VECTOR_SIZE_EMBEDDING for _ in texts]

        monkeypatch.setattr(qc_mod, "llm_embed_async", fake_embed_async)
        c = QdrantClient(_config())
        out = c.generar_embedding("t")
        assert out[0] == 0.5
        assert recibidos == [["t"]]

    def test_generar_embedding_sync_en_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        recibidos: list[str] = []

        async def fake_embed_async(texts, model=None):
            recibidos.append(texts)
            return [[0.5] * VECTOR_SIZE_EMBEDDING for _ in texts]

        monkeypatch.setattr(qc_mod, "llm_embed_async", fake_embed_async)
        c = QdrantClient(_config())

        async def main() -> list[float]:
            return c.generar_embedding("t")

        out = asyncio.run(main())
        assert out[0] == 0.5
        assert recibidos == [["t"]]

    def test_generar_embeddings_batch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(qc_mod, "llm_embed", lambda texts, model=None: [[0.1]] * len(texts))
        c = QdrantClient(_config())
        assert c.generar_embeddings_batch(["a", "b"]) == [[0.1], [0.1]]


# ── URAQdrantClient (async) ──────────────────────────────────────────────────


class FakeAsyncResp:
    def __init__(self, status: int = 200, data: dict | None = None) -> None:
        self.status_code = status
        self._data = data or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}",
                request=httpx.Request("POST", "http://fake"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self._data


class FakeAsyncClient2:
    def __init__(self, responses: list[Any] | None = None) -> None:
        self.responses = list(responses or [])
        self.posts: list[tuple[str, dict]] = []
        self.puts: list[tuple[str, dict]] = []
        self.gets: list[str] = []
        self.closed = False
        self.is_closed = False

    async def post(self, url: str, **kw: Any) -> Any:
        self.posts.append((url, kw.get("json", {})))
        return self._next()

    async def put(self, url: str, **kw: Any) -> Any:
        self.puts.append((url, kw.get("json", {})))
        return self._next()

    async def get(self, url: str) -> Any:
        self.gets.append(url)
        return self._next()

    def _next(self) -> Any:
        if not self.responses:
            return FakeAsyncResp()
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    async def aclose(self) -> None:
        self.closed = True
        self.is_closed = True


class TestURAQdrantClient:
    def test_get_client_crea_y_reusa(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2()

        async def main() -> None:
            c1 = await c._get_client()
            c2 = await c._get_client()
            assert c1 is c2

        asyncio.run(main())

    def test_get_client_recrea_si_closed(self) -> None:
        c = URAQdrantClient()
        viejo = FakeAsyncClient2()
        viejo.is_closed = True
        c._client = viejo

        async def main() -> None:
            nuevo = await c._get_client()
            assert nuevo is not viejo

        asyncio.run(main())

    def test_buscar_vectores_ok(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([FakeAsyncResp(200, {"result": [1]})])

        async def main() -> None:
            out = await c.buscar_vectores("col", [0.1])
            assert out == {"result": [1]}

        asyncio.run(main())

    def test_buscar_vectores_http_error(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([FakeAsyncResp(500, {"detail": "x"})])

        async def main() -> None:
            out = await c.buscar_vectores("col", [0.1])
            assert out == {"result": []}

        asyncio.run(main())

    def test_buscar_vectores_request_error(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([httpx.RequestError("net")])

        async def main() -> None:
            out = await c.buscar_vectores("col", [0.1])
            assert out == {"result": []}

        asyncio.run(main())

    def test_upsert_ok(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([FakeAsyncResp(200)])

        async def main() -> None:
            assert await c.upsert_puntos("col", [{"id": 1}]) == 1

        asyncio.run(main())

    def test_upsert_error(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([httpx.RequestError("x")])

        async def main() -> None:
            assert await c.upsert_puntos("col", [{"id": 1}]) == 0

        asyncio.run(main())

    def test_close(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2()

        async def main() -> None:
            await c.close()
            assert c._client.closed is True
            c._client = None
            await c.close()  # sin cliente

        asyncio.run(main())

    def test_asegurar_hibrida_existe(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([FakeAsyncResp(200)])

        async def main() -> None:
            assert await c.asegurar_coleccion_hibrida("col") is True

        asyncio.run(main())

    def test_asegurar_hibrida_crea(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([FakeAsyncResp(404), FakeAsyncResp(201)])

        async def main() -> None:
            assert await c.asegurar_coleccion_hibrida("col") is True

        asyncio.run(main())

    def test_asegurar_hibrida_get_error(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([httpx.RequestError("x"), FakeAsyncResp(200)])

        async def main() -> None:
            assert await c.asegurar_coleccion_hibrida("col") is True

        asyncio.run(main())

    def test_asegurar_hibrida_put_error(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([FakeAsyncResp(404), httpx.RequestError("x")])

        async def main() -> None:
            assert await c.asegurar_coleccion_hibrida("col") is False

        asyncio.run(main())

    def test_buscar_hibrido_ok(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([FakeAsyncResp(200, {"result": [{"id": 1}]})])

        async def main() -> None:
            out = await c.buscar_hibrido("col", "query", [0.1])
            assert out == [{"id": 1}]

        asyncio.run(main())

    def test_buscar_hibrido_fallback(self) -> None:
        c = URAQdrantClient()
        c._client = FakeAsyncClient2([httpx.RequestError("x"), FakeAsyncResp(200, {"result": [{"id": 2}]})])

        async def main() -> None:
            out = await c.buscar_hibrido("col", "query", [0.1])
            assert out == [{"id": 2}]

        asyncio.run(main())


class TestRamasRestFaltantes:
    def _cliente_rest(self, monkeypatch: pytest.MonkeyPatch, get_status: int, put_status: int) -> QdrantClient:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=get_status))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=put_status))
        monkeypatch.setattr(httpx, "post", lambda *a, **k: SimpleNamespace(status_code=200))
        return QdrantClient(_config())

    def test_rest_404_crea_todas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = self._cliente_rest(monkeypatch, get_status=404, put_status=200)
        assert c.disponible is True
        assert c._modo_rest is True

    def test_rest_put_falla_except(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=404))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("put")))
        c = QdrantClient(_config())
        assert c.disponible is True  # asegurar_colleccion solo loguea, no degrada

    def test_cliente_none_guardar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient()
        _instalar_qdrant_fake(monkeypatch, native)
        c = QdrantClient(_config())
        c._cliente = None
        monkeypatch.setattr(qc_mod, "llm_embed", lambda texts, model=None: [[0.1]] * len(texts))
        assert c.guardar_documento("d", "t") is False
        assert c.buscar_por_similitud([0.1]) == []
        assert c.eliminar_por_filtro({"k": "v"}) is False
        assert c.guardar_incidente({"ts": "x"}) is False
        assert c.buscar_incidentes() == []
        assert c.health() is False

    def test_rest_guardar_error_except(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        c = QdrantClient(_config())
        monkeypatch.setattr(qc_mod, "llm_embed", lambda texts, model=None: [[0.1]] * len(texts))
        assert c.guardar_documento("d", "t") is False

    def test_buscar_rest_status_no_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=201))
        monkeypatch.setattr(httpx, "post", lambda *a, **k: SimpleNamespace(status_code=500))
        c = QdrantClient(_config())
        assert c.buscar_por_similitud([0.1]) == []

    def test_buscar_incidentes_rest_no_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=200))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=201))
        monkeypatch.setattr(httpx, "post", lambda *a, **k: SimpleNamespace(status_code=500))
        c = QdrantClient(_config())
        assert c.buscar_incidentes() == []

    def test_health_rest_con_cliente_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = self._cliente_rest(monkeypatch, get_status=200, put_status=201)
        c._cliente = None
        assert c.health() is True  # modo_rest -> mark_healthy sin cliente


class TestRamasRestFinales:
    def test_rest_status_500_no_degrada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=500))
        c = QdrantClient(_config())
        assert c.disponible is False

    def test_rest_put_status_500_crea_no_loguea(self, monkeypatch: pytest.MonkeyPatch) -> None:
        native = FakeNativeClient(collections_ok=False)
        _instalar_qdrant_fake(monkeypatch, native)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: SimpleNamespace(status_code=404))
        monkeypatch.setattr(httpx, "put", lambda *a, **k: SimpleNamespace(status_code=500))
        c = QdrantClient(_config())
        assert c.disponible is True
        assert c._modo_rest is True
