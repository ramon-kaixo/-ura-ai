"""Unit tests para motor/core/qdrant_client.py — cobertura completa.

Cubre: _conectar (nativo/REST/degradado), _asegurar_coleccion*, guardado,
búsqueda, eliminación, incidentes, singleton y URAQdrantClient async.

Mock permitido: httpx, qdrant_client (librería nativa, no instalada), DegradedMode.
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import motor.core.qdrant_client as qc_mod
from motor.core.config import UraConfig
from motor.core.qdrant_client import (
    COLECCION_DOCUMENTOS,
    COLECCION_INCIDENTES,
    COLECCION_TRANSACCIONES,
    VECTOR_SIZE_EMBEDDING,
    QdrantClient,
    URAQdrantClient,
)


class UnexpectedResponse(Exception):
    """Fake de qdrant_client.http.exceptions.UnexpectedResponse."""


class FakeDistance:
    COSINE = "Cosine"


class FakeVectorParams:
    def __init__(self, size: int | None = None, distance: str | None = None) -> None:
        self.size = size
        self.distance = distance


class FakePointStruct:
    def __init__(self, id: int | None = None, vector: list | None = None, payload: dict | None = None) -> None:  # noqa: A002
        self.id = id
        self.vector = vector
        self.payload = payload


class FakeMatchValue:
    def __init__(self, value: object | None = None) -> None:
        self.value = value


class FakeFieldCondition:
    def __init__(self, key: str | None = None, match: FakeMatchValue | None = None) -> None:
        self.key = key
        self.match = match


class FakeFilter:
    def __init__(self, must: list | None = None) -> None:
        self.must = must


class FakeFilterSelector:
    def __init__(self, filter: FakeFilter | None = None) -> None:  # noqa: A002
        self.filter = filter


class FakeModels:
    Distance = FakeDistance
    VectorParams = FakeVectorParams
    PointStruct = FakePointStruct
    MatchValue = FakeMatchValue
    FieldCondition = FakeFieldCondition
    Filter = FakeFilter
    FilterSelector = FakeFilterSelector


class FakeQC:
    """Fake de la librería nativa qdrant_client.QdrantClient."""

    def __init__(self, host: str | None = None, port: int | None = None, timeout: int | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.existing: list[str] = []
        self.created: list[str] = []
        self.upserted: tuple[str, list] | None = None
        self.deleted: tuple[str, object] | None = None
        self.scroll_result: tuple[list, object] | None = None
        self.query_result: object | None = None
        self.fail_get_collections = False
        self.fail_upsert = False
        self.fail_query = False
        self.fail_delete = False
        self.fail_scroll = False
        self.get_collection_error: Exception | None = None

    def get_collections(self) -> list:
        if self.fail_get_collections:
            raise RuntimeError("conn refused")
        return []

    def get_collection(self, name: str) -> bool:
        if self.get_collection_error is not None:
            raise self.get_collection_error
        if name in self.existing:
            return True
        raise UnexpectedResponse("not found")

    def recreate_collection(self, collection_name: str | None = None, vectors_config: object | None = None) -> None:
        self.created.append(collection_name or "")

    def upsert(self, collection_name: str | None = None, points: list | None = None) -> None:
        if self.fail_upsert:
            raise RuntimeError("upsert fail")
        self.upserted = (collection_name or "", points or [])

    def query_points(self, collection_name: str | None = None, query: object | None = None, limit: int | None = None) -> object:
        if self.fail_query:
            raise RuntimeError("query fail")
        return self.query_result

    def delete(self, collection_name: str | None = None, points_selector: object | None = None) -> None:
        if self.fail_delete:
            raise RuntimeError("delete fail")
        self.deleted = (collection_name or "", points_selector)

    def scroll(self, collection_name: str | None = None, limit: int | None = None) -> tuple[list, object]:
        if self.fail_scroll:
            raise RuntimeError("scroll fail")
        return self.scroll_result or ([], None)


class FakeResp:
    def __init__(self, status_code: int = 200, json_data: dict | None = None) -> None:
        self.status_code = status_code
        self._json = json_data or {}

    def json(self) -> dict:
        return self._json


def make_config() -> MagicMock:
    config = MagicMock(spec=UraConfig)
    config.qdrant_host = "127.0.0.1"
    config.qdrant_port = 6333
    config.schema_version = "3.1"
    return config


@pytest.fixture
def native_modules() -> dict:
    """Módulos fake de la librería qdrant_client (imports intrafunción)."""
    qdrant = ModuleType("qdrant_client")
    http = ModuleType("qdrant_client.http")
    exceptions = ModuleType("qdrant_client.http.exceptions")
    models = ModuleType("qdrant_client.http.models")
    exceptions.UnexpectedResponse = UnexpectedResponse
    models.VectorParams = FakeVectorParams
    models.Distance = FakeDistance
    models.PointStruct = FakePointStruct
    models.MatchValue = FakeMatchValue
    models.FieldCondition = FakeFieldCondition
    models.Filter = FakeFilter
    models.FilterSelector = FakeFilterSelector
    http.exceptions = exceptions
    http.models = models
    qdrant.http = http
    qdrant.QdrantClient = FakeQC
    return {
        "qdrant_client": qdrant,
        "qdrant_client.http": http,
        "qdrant_client.http.exceptions": exceptions,
        "qdrant_client.http.models": models,
    }


@pytest.fixture
def client() -> QdrantClient:
    with patch.object(QdrantClient, "_conectar"):
        return QdrantClient(make_config())


# ===================================================================
# _conectar — nativo, REST fallback, degradado
# ===================================================================

class TestConectar:
    @patch("motor.core.qdrant_client.DegradedMode")
    def test_conectar_nativo_ok(self, mock_dm: MagicMock, native_modules: dict) -> None:
        with patch.dict(sys.modules, native_modules):
            c = QdrantClient(make_config())
        assert c.disponible is True
        assert c._modo_rest is False
        assert isinstance(c._cliente, FakeQC)
        assert c._cliente.created == [COLECCION_INCIDENTES, COLECCION_DOCUMENTOS, COLECCION_TRANSACCIONES]
        mock_dm.instancia().mark_healthy.assert_called_with("qdrant")

    @patch("motor.core.qdrant_client.DegradedMode")
    @patch("motor.core.qdrant_client.httpx.put")
    @patch("motor.core.qdrant_client.httpx.get")
    def test_conectar_rest_fallback(self, mock_get: MagicMock, mock_put: MagicMock, mock_dm: MagicMock, native_modules: dict) -> None:
        def fake_get(url: str, timeout: float | None = None) -> FakeResp:
            return FakeResp(200) if url.endswith("/collections") else FakeResp(404)

        mock_get.side_effect = fake_get
        mock_put.return_value = FakeResp(201)
        qc = FakeQC()
        qc.fail_get_collections = True
        native_modules["qdrant_client"].QdrantClient = lambda host=None, port=None, timeout=None: qc
        with patch.dict(sys.modules, native_modules):
            c = QdrantClient(make_config())
        assert c.disponible is True
        assert c._modo_rest is True
        assert c._cliente is None
        assert len(mock_put.call_args_list) == 3
        mock_dm.instancia().mark_healthy.assert_called_with("qdrant")

    @patch("motor.core.qdrant_client.DegradedMode")
    @patch("motor.core.qdrant_client.httpx.get")
    def test_conectar_degradado(self, mock_get: MagicMock, mock_dm: MagicMock, native_modules: dict) -> None:
        qc = FakeQC()
        qc.fail_get_collections = True
        native_modules["qdrant_client"].QdrantClient = lambda host=None, port=None, timeout=None: qc
        mock_get.side_effect = OSError("no net")
        with patch.dict(sys.modules, native_modules):
            c = QdrantClient(make_config())
        assert c.disponible is False
        assert c._cliente is qc
        mock_dm.instancia().mark_degraded.assert_called_with("qdrant")

    @patch("motor.core.qdrant_client.DegradedMode")
    @patch("motor.core.qdrant_client.httpx.get")
    def test_conectar_rest_status_500(self, mock_get: MagicMock, mock_dm: MagicMock, native_modules: dict) -> None:
        qc = FakeQC()
        qc.fail_get_collections = True
        native_modules["qdrant_client"].QdrantClient = lambda host=None, port=None, timeout=None: qc
        mock_get.return_value = FakeResp(500)
        with patch.dict(sys.modules, native_modules):
            c = QdrantClient(make_config())
        assert c.disponible is False
        mock_dm.instancia().mark_degraded.assert_called_with("qdrant")


# ===================================================================
# _asegurar_coleccion* — REST y nativo
# ===================================================================

class TestAsegurarColecciones:
    @pytest.mark.parametrize(
        ("metodo", "coleccion"),
        [
            ("_asegurar_coleccion", COLECCION_INCIDENTES),
            ("_asegurar_coleccion_documentos", COLECCION_DOCUMENTOS),
            ("_asegurar_coleccion_transacciones", COLECCION_TRANSACCIONES),
        ],
    )
    def test_rest_creates_on_404(self, client: QdrantClient, metodo: str, coleccion: str) -> None:
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "get") as mget, patch.object(qc_mod.httpx, "put") as mput:
            mget.return_value = FakeResp(404)
            mput.return_value = FakeResp(201)
            getattr(client, metodo)()
        assert mget.called
        assert mput.called
        assert coleccion in mput.call_args[0][0]

    @pytest.mark.parametrize("metodo", ["_asegurar_coleccion", "_asegurar_coleccion_documentos"])
    def test_rest_200_noop(self, client: QdrantClient, metodo: str) -> None:
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "get") as mget, patch.object(qc_mod.httpx, "put") as mput:
            mget.return_value = FakeResp(200)
            getattr(client, metodo)()
        assert mput.call_count == 0

    def test_rest_put_non_2xx(self, client: QdrantClient) -> None:
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "get") as mget, patch.object(qc_mod.httpx, "put") as mput:
            mget.return_value = FakeResp(404)
            mput.return_value = FakeResp(500)
            client._asegurar_coleccion()
        assert mput.called

    def test_rest_get_error(self, client: QdrantClient) -> None:
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "get") as mget:
            mget.side_effect = OSError("net")
            client._asegurar_coleccion()

    @pytest.mark.parametrize(
        ("metodo", "coleccion"),
        [
            ("_asegurar_coleccion", COLECCION_INCIDENTES),
            ("_asegurar_coleccion_documentos", COLECCION_DOCUMENTOS),
            ("_asegurar_coleccion_transacciones", COLECCION_TRANSACCIONES),
        ],
    )
    def test_native_creates(self, client: QdrantClient, native_modules: dict, metodo: str, coleccion: str) -> None:
        client._modo_rest = False
        qc = FakeQC()
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            getattr(client, metodo)()
        assert qc.created == [coleccion]
        assert qc.created[0] == coleccion

    @pytest.mark.parametrize("metodo", ["_asegurar_coleccion", "_asegurar_coleccion_documentos"])
    def test_native_exists(self, client: QdrantClient, native_modules: dict, metodo: str) -> None:
        client._modo_rest = False
        qc = FakeQC()
        qc.existing = [COLECCION_INCIDENTES, COLECCION_DOCUMENTOS, COLECCION_TRANSACCIONES]
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            getattr(client, metodo)()
        assert qc.created == []

    def test_native_other_error(self, client: QdrantClient, native_modules: dict) -> None:
        client._modo_rest = False
        qc = FakeQC()
        qc.get_collection_error = RuntimeError("boom")
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            client._asegurar_coleccion()
        assert qc.created == []

    @pytest.mark.parametrize(
        "metodo",
        ["_asegurar_coleccion_documentos", "_asegurar_coleccion_transacciones"],
    )
    def test_native_other_error_restantes(self, client: QdrantClient, native_modules: dict, metodo: str) -> None:
        client._modo_rest = False
        qc = FakeQC()
        qc.get_collection_error = RuntimeError("boom")
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            getattr(client, metodo)()
        assert qc.created == []


# ===================================================================
# Embeddings async
# ===================================================================

class TestGenerarEmbeddingAsync:
    def test_ok(self, client: QdrantClient) -> None:
        with patch.object(client, "generar_embeddings_batch_async", new=AsyncMock(return_value=[[0.1, 0.2]])):
            out = asyncio.run(client.generar_embedding_async("texto"))
        assert out == [0.1, 0.2]

    def test_zero_vector(self, client: QdrantClient) -> None:
        with patch.object(client, "generar_embeddings_batch_async", new=AsyncMock(return_value=[[0.0, 0.0]])):
            out = asyncio.run(client.generar_embedding_async("texto"))
        assert out == [0.0] * VECTOR_SIZE_EMBEDDING

    def test_empty_result(self, client: QdrantClient) -> None:
        with patch.object(client, "generar_embeddings_batch_async", new=AsyncMock(return_value=[])):
            out = asyncio.run(client.generar_embedding_async("texto"))
        assert out == [0.0] * VECTOR_SIZE_EMBEDDING

    def test_batch_async_delega_en_llm(self, client: QdrantClient) -> None:
        with patch("motor.core.qdrant_client.llm_embed_async", new=AsyncMock(return_value=[[0.1]])) as m:
            out = asyncio.run(client.generar_embeddings_batch_async(["x"]))
        m.assert_awaited_with(["x"], model="nomic-embed-text")
        assert out == [[0.1]]


# ===================================================================
# Guardar documentos
# ===================================================================

class TestGuardarDocumentos:
    def test_no_disponible(self, client: QdrantClient) -> None:
        client.disponible = False
        assert client._guardar_documentos([("a", "texto", {})]) == 0

    def test_empty_docs(self, client: QdrantClient) -> None:
        assert client._guardar_documentos([]) == 0

    def test_rest_ok(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1], [0.2]]), patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(200)
            n = client._guardar_documentos([("a", "hola", {"x": 1}), ("b", "mundo", {})])
        assert n == 2
        points = mput.call_args[1]["json"]["points"]
        assert len(points) == 2
        assert points[0]["payload"]["id"] == "a"
        assert points[0]["payload"]["x"] == 1
        assert points[0]["payload"]["texto"] == "hola"

    def test_rest_500(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(500)
            assert client._guardar_documentos([("a", "t", {})]) == 0

    def test_rest_error(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.object(qc_mod.httpx, "put") as mput:
            mput.side_effect = OSError("net")
            assert client._guardar_documentos([("a", "t", {})]) == 0

    def test_native_ok(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        client._cliente = qc
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.dict(sys.modules, native_modules):
            n = client._guardar_documentos([("a", "hola", {"x": 1})])
        assert n == 1
        coleccion, points = qc.upserted
        assert coleccion == COLECCION_DOCUMENTOS
        assert points[0].payload["x"] == 1
        assert points[0].vector == [0.1]

    def test_native_sin_cliente(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = False
        client._cliente = None
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]):
            assert client._guardar_documentos([("a", "t", {})]) == 0

    def test_native_error(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.fail_upsert = True
        client._cliente = qc
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.dict(sys.modules, native_modules):
            assert client._guardar_documentos([("a", "t", {})]) == 0

    def test_doc_id_vacio_usa_texto(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(200)
            client._guardar_documentos([("", "texto unico", {})])
        pid = mput.call_args[1]["json"]["points"][0]["id"]
        expected = int(hashlib.sha256(b"texto unico").hexdigest()[:15], 16) % (2**63)
        assert pid == expected

    def test_pid_determinista(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(200)
            client._guardar_documentos([("doc-1", "texto", {})])
        pid = mput.call_args[1]["json"]["points"][0]["id"]
        expected = int(hashlib.sha256(b"doc-1").hexdigest()[:15], 16) % (2**63)
        assert pid == expected

    def test_guardar_documento(self, client: QdrantClient) -> None:
        client.disponible = True
        with patch.object(client, "_guardar_documentos", return_value=1) as m:
            assert client.guardar_documento("d1", "texto", {"a": 1}) is True
        m.assert_called_with([("d1", "texto", {"a": 1})], COLECCION_DOCUMENTOS)

    def test_guardar_documento_false(self, client: QdrantClient) -> None:
        client.disponible = True
        with patch.object(client, "_guardar_documentos", return_value=0):
            assert client.guardar_documento("d1", "texto") is False

    def test_guardar_documento_metadata_none(self, client: QdrantClient) -> None:
        client.disponible = True
        with patch.object(client, "_guardar_documentos", return_value=1) as m:
            client.guardar_documento("d1", "texto", None)
        m.assert_called_with([("d1", "texto", {})], COLECCION_DOCUMENTOS)

    def test_guardar_documentos_batch(self, client: QdrantClient) -> None:
        client.disponible = True
        docs = [("a", "t1", {}), ("b", "t2", {})]
        with patch.object(client, "_guardar_documentos", return_value=2) as m:
            assert client.guardar_documentos_batch(docs, "otra") == 2
        m.assert_called_with(docs, "otra")


# ===================================================================
# Buscar por similitud
# ===================================================================

class TestBuscarPorSimilitud:
    def test_no_disponible(self, client: QdrantClient) -> None:
        assert client.buscar_por_similitud([0.1]) == []

    def test_rest_ok(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.return_value = FakeResp(200, {"result": [{"payload": {"a": 1}, "score": 0.9}]})
            out = client.buscar_por_similitud([0.1, 0.2], limit=3)
        assert out == [{"payload": {"a": 1}, "score": 0.9}]
        payload = mpost.call_args[1]["json"]
        assert payload["limit"] == 3
        assert payload["vector"] == [0.1, 0.2]

    def test_rest_no_200(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.return_value = FakeResp(500)
            assert client.buscar_por_similitud([0.1]) == []

    def test_rest_error(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.side_effect = OSError("net")
            assert client.buscar_por_similitud([0.1]) == []

    def test_native_ok(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.query_result = SimpleNamespace(
            points=[
                SimpleNamespace(payload={"a": 1}, score=0.9),
                SimpleNamespace(payload={"b": 2}, score=0.8),
            ],
        )
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            out = client.buscar_por_similitud([0.1], limit=5)
        assert out == [{"payload": {"a": 1}, "score": 0.9}, {"payload": {"b": 2}, "score": 0.8}]

    def test_native_points_none(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.query_result = SimpleNamespace(points=None)
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.buscar_por_similitud([0.1]) == []

    def test_native_sin_cliente(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = False
        client._cliente = None
        assert client.buscar_por_similitud([0.1]) == []

    def test_native_error(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.fail_query = True
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.buscar_por_similitud([0.1]) == []

    def test_buscar_documentos(self, client: QdrantClient) -> None:
        client.disponible = True
        with patch.object(client, "generar_embedding", return_value=[0.5]) as memb, patch.object(
            client, "buscar_por_similitud", return_value=[{"payload": {}}]
        ) as mbus:
            out = client.buscar_documentos("consulta")
        memb.assert_called_with("consulta")
        mbus.assert_called_with([0.5], COLECCION_DOCUMENTOS, 10)
        assert out == [{"payload": {}}]


# ===================================================================
# Eliminar por filtro (vía pública + REST)
# ===================================================================

class TestEliminarPorFiltro:
    def test_no_disponible(self, client: QdrantClient) -> None:
        assert client.eliminar_por_filtro({"a": 1}) is False

    def test_rest_dispatch(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(client, "_eliminar_por_filtro_rest", return_value=True) as m:
            assert client.eliminar_por_filtro({"a": 1}) is True
        m.assert_called_with({"a": 1}, COLECCION_DOCUMENTOS)

    def test_native_sin_cliente(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = False
        client._cliente = None
        assert client.eliminar_por_filtro({"a": 1}) is False

    def test_native_ok(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.eliminar_por_filtro({"source": "x"}) is True
        coleccion, selector = qc.deleted
        assert coleccion == COLECCION_DOCUMENTOS
        assert selector.filter.must[0].key == "source"
        assert selector.filter.must[0].match.value == "x"

    def test_native_error(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.fail_delete = True
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.eliminar_por_filtro({"a": 1}) is False

    def test_rest_error(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.side_effect = OSError("net")
            assert client._eliminar_por_filtro_rest({"a": 1}, "c") is False


# ===================================================================
# Incidentes
# ===================================================================

class TestGuardarIncidente:
    def test_no_disponible(self, client: QdrantClient) -> None:
        assert client.guardar_incidente({}) is False

    def test_rest_dispatch(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(client, "_guardar_rest", return_value=True) as m:
            assert client.guardar_incidente({"ts": "t"}) is True
        m.assert_called_with({"ts": "t"})

    def test_native_sin_cliente(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = False
        client._cliente = None
        assert client.guardar_incidente({}) is False

    def test_native_ok(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        client._cliente = qc
        incidente = {"ts": "2026-01-01T00:00:00", "impacto_memoria": [0.5] * 7, "tipo": "CRASH"}
        with patch.dict(sys.modules, native_modules):
            assert client.guardar_incidente(incidente) is True
        coleccion, points = qc.upserted
        assert coleccion == COLECCION_INCIDENTES
        assert points[0].payload["tipo_incidencia"] == "CRASH"
        assert points[0].vector == [0.5] * 7

    def test_native_error(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.fail_upsert = True
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.guardar_incidente({}) is False


class TestGuardarRest:
    def test_ok(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(201)
            assert client._guardar_rest({"ts": "2026-01-01T00:00:00"}) is True
        point = mput.call_args[1]["json"]["points"][0]
        assert point["vector"] == [0.0] * 7
        assert point["payload"]["tipo_incidencia"] == "Unknown"

    def test_no_2xx(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(500)
            assert client._guardar_rest({}) is False

    def test_error(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "put") as mput:
            mput.side_effect = OSError("net")
            assert client._guardar_rest({}) is False


class TestBuscarIncidentes:
    def test_no_disponible(self, client: QdrantClient) -> None:
        assert client.buscar_incidentes() == []

    def test_rest_ok(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.return_value = FakeResp(
                200, {"result": {"points": [{"payload": {"tipo": "X"}}, {"payload": {"tipo": "Y"}}]}}
            )
            out = client.buscar_incidentes()
        assert out == [{"tipo": "X"}, {"tipo": "Y"}]

    def test_rest_no_200(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.return_value = FakeResp(500)
            assert client.buscar_incidentes() == []

    def test_rest_error(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.side_effect = OSError("net")
            assert client.buscar_incidentes() == []

    def test_native_ok(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.scroll_result = ([SimpleNamespace(payload={"a": 1}), SimpleNamespace(payload={"b": 2})], None)
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            out = client.buscar_incidentes(limit=2)
        assert out == [{"a": 1}, {"b": 2}]

    def test_native_sin_payload(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.scroll_result = ([SimpleNamespace(no_payload=1)], None)
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.buscar_incidentes() == []

    def test_native_sin_cliente(self, client: QdrantClient) -> None:
        client.disponible = True
        client._modo_rest = False
        client._cliente = None
        assert client.buscar_incidentes() == []

    def test_native_error(self, client: QdrantClient, native_modules: dict) -> None:
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.fail_scroll = True
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.buscar_incidentes() == []


# ===================================================================
# Singleton
# ===================================================================

class TestInstancia:
    def test_singleton(self, native_modules: dict) -> None:
        QdrantClient._instancia = None
        try:
            with patch.object(QdrantClient, "_conectar"), patch.dict(sys.modules, native_modules):
                a = QdrantClient.instancia(make_config())
                b = QdrantClient.instancia(make_config())
            assert a is b
        finally:
            QdrantClient._instancia = None


# ===================================================================
# URAQdrantClient — async con connection pooling
# ===================================================================

class TestURAQdrantClient:
    def _client(self) -> AsyncMock:
        c = AsyncMock()
        c.is_closed = False
        return c

    def test_get_client_lazy(self) -> None:
        ura = URAQdrantClient("http://test:6333", timeout=5.0)
        fake = self._client()
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=fake) as m:
            c1 = asyncio.run(ura._get_client())
            c2 = asyncio.run(ura._get_client())
        assert c1 is c2
        m.assert_called_once_with(
            base_url="http://test:6333",
            timeout=5.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

    def test_get_client_recreates_when_closed(self) -> None:
        ura = URAQdrantClient()
        a = self._client()
        b = self._client()
        with patch.object(qc_mod.httpx, "AsyncClient", side_effect=[a, b]):
            c1 = asyncio.run(ura._get_client())
            a.is_closed = True
            c2 = asyncio.run(ura._get_client())
        assert c1 is a
        assert c2 is b

    def test_buscar_vectores_ok(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        resp = MagicMock()
        resp.json.return_value = {"result": [{"payload": {}}]}
        client.post.return_value = resp
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            out = asyncio.run(ura.buscar_vectores("colec", [0.1], limite=3))
        assert out == {"result": [{"payload": {}}]}
        args = client.post.call_args
        assert args[0][0] == "/collections/colec/points/search"
        assert args[1]["json"] == {"vector": [0.1], "limit": 3, "with_payload": True}

    def test_buscar_vectores_http_error(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        req = httpx.Request("POST", "http://test")
        resp = httpx.Response(500, request=req)
        client.post.side_effect = httpx.HTTPStatusError("boom", request=req, response=resp)
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            out = asyncio.run(ura.buscar_vectores("c", [0.1]))
        assert out == {"result": []}

    def test_buscar_vectores_network_error(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        client.post.side_effect = httpx.RequestError("net", request=httpx.Request("POST", "http://test"))
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            out = asyncio.run(ura.buscar_vectores("c", [0.1]))
        assert out == {"result": []}

    def test_upsert_ok(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            n = asyncio.run(ura.upsert_puntos("c", [{"id": 1}]))
        assert n == 1
        args = client.put.call_args
        assert args[0][0] == "/collections/c/points"
        assert args[1]["json"] == {"points": [{"id": 1}]}

    def test_upsert_error(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        client.put.side_effect = OSError("net")
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            n = asyncio.run(ura.upsert_puntos("c", [{"id": 1}]))
        assert n == 0

    def test_close(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            asyncio.run(ura._get_client())
            asyncio.run(ura.close())
        client.aclose.assert_awaited_once()

    def test_close_closed_client(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        client.is_closed = True
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            asyncio.run(ura.close())
        client.aclose.assert_not_called()

    def test_asegurar_coleccion_hibrida_existe(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        client.get.return_value = MagicMock(status_code=200)
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            ok = asyncio.run(ura.asegurar_coleccion_hibrida("c"))
        assert ok is True
        client.put.assert_not_called()

    def test_asegurar_coleccion_hibrida_crea(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        client.get.return_value = MagicMock(status_code=404)
        client.put.return_value = MagicMock(status_code=201)
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            ok = asyncio.run(ura.asegurar_coleccion_hibrida("c"))
        assert ok is True
        payload = client.put.call_args[1]["json"]
        assert payload["vectors"]["size"] == VECTOR_SIZE_EMBEDDING
        assert payload["sparse_vectors"]["bm25"]["modifier"] == "idf"

    def test_asegurar_coleccion_hibrida_get_error(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        client.get.side_effect = OSError("net")
        client.put.return_value = MagicMock(status_code=201)
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            ok = asyncio.run(ura.asegurar_coleccion_hibrida("c"))
        assert ok is True

    def test_asegurar_coleccion_hibrida_put_error(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        client.get.return_value = MagicMock(status_code=404)
        client.put.side_effect = OSError("net")
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            ok = asyncio.run(ura.asegurar_coleccion_hibrida("c"))
        assert ok is False

    def test_buscar_hibrido_ok(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        resp = MagicMock()
        resp.json.return_value = {"result": [{"payload": {"x": 1}}]}
        client.post.return_value = resp
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            out = asyncio.run(ura.buscar_hibrido("c", "consulta", [0.1], limite=5))
        assert out == [{"payload": {"x": 1}}]
        payload = client.post.call_args[1]["json"]
        assert len(payload["prefetch"]) == 2
        assert payload["query"] == {"fusion": "rrf"}
        assert payload["limit"] == 5

    def test_buscar_hibrido_fallback_denso(self) -> None:
        ura = URAQdrantClient()
        client = self._client()
        client.post.side_effect = httpx.RequestError("net", request=httpx.Request("POST", "http://test"))
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client), patch.object(
            ura, "buscar_vectores", new=AsyncMock(return_value={"result": [{"payload": {"fallback": True}}]})
        ):
            out = asyncio.run(ura.buscar_hibrido("c", "q", [0.1]))
        assert out == [{"payload": {"fallback": True}}]
