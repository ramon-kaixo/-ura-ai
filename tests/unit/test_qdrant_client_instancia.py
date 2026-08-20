"""Tests cobertura motor qdrant_client — instancia/incidentes (split)."""
from __future__ import annotations

from _qdrant_helpers import (  # noqa: F401
    VECTOR_SIZE_EMBEDDING,
    AsyncMock,
    FakeQC,
    FakeResp,
    MagicMock,
    QdrantClient,
    SimpleNamespace,
    URAQdrantClient,
    asyncio,
    client,
    httpx,
    json,
    make_config,
    native_modules,
    patch,
    qc_mod,
    sys,
)


class TestBuscarIncidentes:
    def test_no_disponible(self, client: QdrantClient) -> None:  # noqa: F811
        assert client.buscar_incidentes() == []

    def test_rest_ok(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.return_value = FakeResp(
                200, {"result": {"points": [{"payload": {"tipo": "X"}}, {"payload": {"tipo": "Y"}}]}}
            )
            out = client.buscar_incidentes()
        assert out == [{"tipo": "X"}, {"tipo": "Y"}]

    def test_rest_no_200(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.return_value = FakeResp(500)
            assert client.buscar_incidentes() == []

    def test_rest_error(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.side_effect = OSError("net")
            assert client.buscar_incidentes() == []

    def test_native_ok(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.scroll_result = ([SimpleNamespace(payload={"a": 1}), SimpleNamespace(payload={"b": 2})], None)
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            out = client.buscar_incidentes(limit=2)
        assert out == [{"a": 1}, {"b": 2}]

    def test_native_sin_payload(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.scroll_result = ([SimpleNamespace(no_payload=1)], None)
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.buscar_incidentes() == []

    def test_native_sin_cliente(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        client._cliente = None
        assert client.buscar_incidentes() == []

    def test_native_error(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
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
    def test_singleton(self, native_modules: dict) -> None:  # noqa: F811
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
        client = self._client()  # noqa: F811
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
        client = self._client()  # noqa: F811
        req = httpx.Request("POST", "http://test")
        resp = httpx.Response(500, request=req)
        client.post.side_effect = httpx.HTTPStatusError("boom", request=req, response=resp)
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            out = asyncio.run(ura.buscar_vectores("c", [0.1]))
        assert out == {"result": []}

    def test_buscar_vectores_network_error(self) -> None:
        ura = URAQdrantClient()
        client = self._client()  # noqa: F811
        client.post.side_effect = httpx.RequestError("net", request=httpx.Request("POST", "http://test"))
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            out = asyncio.run(ura.buscar_vectores("c", [0.1]))
        assert out == {"result": []}

    def test_upsert_ok(self) -> None:
        ura = URAQdrantClient()
        client = self._client()  # noqa: F811
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            n = asyncio.run(ura.upsert_puntos("c", [{"id": 1}]))
        assert n == 1
        args = client.put.call_args
        assert args[0][0] == "/collections/c/points"
        assert args[1]["json"] == {"points": [{"id": 1}]}

    def test_upsert_error(self) -> None:
        ura = URAQdrantClient()
        client = self._client()  # noqa: F811
        client.put.side_effect = OSError("net")
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            n = asyncio.run(ura.upsert_puntos("c", [{"id": 1}]))
        assert n == 0

    def test_close(self) -> None:
        ura = URAQdrantClient()
        client = self._client()  # noqa: F811
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            asyncio.run(ura._get_client())
            asyncio.run(ura.close())
        client.aclose.assert_awaited_once()

    def test_close_closed_client(self) -> None:
        ura = URAQdrantClient()
        client = self._client()  # noqa: F811
        client.is_closed = True
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            asyncio.run(ura.close())
        client.aclose.assert_not_called()

    def test_asegurar_coleccion_hibrida_existe(self) -> None:
        ura = URAQdrantClient()
        client = self._client()  # noqa: F811
        client.get.return_value = MagicMock(status_code=200)
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            ok = asyncio.run(ura.asegurar_coleccion_hibrida("c"))
        assert ok is True
        client.put.assert_not_called()

    def test_asegurar_coleccion_hibrida_crea(self) -> None:
        ura = URAQdrantClient()
        client = self._client()  # noqa: F811
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
        client = self._client()  # noqa: F811
        client.get.side_effect = OSError("net")
        client.put.return_value = MagicMock(status_code=201)
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            ok = asyncio.run(ura.asegurar_coleccion_hibrida("c"))
        assert ok is True

    def test_asegurar_coleccion_hibrida_put_error(self) -> None:
        ura = URAQdrantClient()
        client = self._client()  # noqa: F811
        client.get.return_value = MagicMock(status_code=404)
        client.put.side_effect = OSError("net")
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client):
            ok = asyncio.run(ura.asegurar_coleccion_hibrida("c"))
        assert ok is False

    def test_buscar_hibrido_ok(self) -> None:
        ura = URAQdrantClient()
        client = self._client()  # noqa: F811
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
        client = self._client()  # noqa: F811
        client.post.side_effect = httpx.RequestError("net", request=httpx.Request("POST", "http://test"))
        with patch.object(qc_mod.httpx, "AsyncClient", return_value=client), patch.object(
            ura, "buscar_vectores", new=AsyncMock(return_value={"result": [{"payload": {"fallback": True}}]})
        ):
            out = asyncio.run(ura.buscar_hibrido("c", "q", [0.1]))
        assert out == [{"payload": {"fallback": True}}]
