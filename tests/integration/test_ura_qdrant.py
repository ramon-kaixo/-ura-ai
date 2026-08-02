"""Integration tests: URAQdrantClient + QdrantClient REST methods (httpx raw).

Mock de red (httpx) SÍ permitido. Mock de lógica interna NO.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from motor.core.qdrant_client import (
    COLECCION_DOCUMENTOS,
    COLECCION_INCIDENTES,
    VECTOR_SIZE,
    QdrantClient,
    UraConfig,
    URAQdrantClient,
)


def _mock_client(mock_resp: AsyncMock) -> AsyncMock:
    """Crea AsyncMock que retorna mock_resp en get/post/put."""
    mc = AsyncMock(spec=httpx.AsyncClient)
    mc.get = AsyncMock(return_value=mock_resp)
    mc.post = AsyncMock(return_value=mock_resp)
    mc.put = AsyncMock(return_value=mock_resp)
    mc.is_closed = False
    mc.aclose = AsyncMock()
    return mc


def _http_resp(status: int = 200, json_data: dict | None = None) -> AsyncMock:
    """Crea una respuesta HTTP con raise_for_status que lanza si status >= 400."""
    data = json_data or {}
    mr = AsyncMock(spec=httpx.Response)
    mr.status_code = status
    mr.json.return_value = data
    if status >= 400:
        mr.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status}", request=MagicMock(), response=mr
        )
    else:
        mr.raise_for_status = MagicMock()
    return mr


# ===================================================================
# URAQdrantClient
# ===================================================================

class TestURAQdrantClient:
    def test_init_defaults(self) -> None:
        client = URAQdrantClient()
        assert client.base_url == "http://127.0.0.1:6333"
        assert client.timeout == 10.0
        assert client._client is None

    @pytest.mark.asyncio
    @patch("motor.core.qdrant_client.httpx.AsyncClient")
    async def test_get_client_lazy_init(self, mock_ac: MagicMock) -> None:
        client = URAQdrantClient()
        assert client._client is None
        await client._get_client()
        mock_ac.assert_called_once_with(
            base_url="http://127.0.0.1:6333",
            timeout=10.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

    @pytest.mark.asyncio
    @patch("motor.core.qdrant_client.httpx.AsyncClient")
    async def test_get_client_reuses_existing(self, mock_ac: MagicMock) -> None:
        client = URAQdrantClient()
        client._client = MagicMock()
        client._client.is_closed = False
        c1 = await client._get_client()
        c2 = await client._get_client()
        assert c1 is c2
        mock_ac.assert_not_called()

    @pytest.mark.asyncio
    async def test_buscar_vectores_success(self) -> None:
        mock_resp = _http_resp(200, {"result": [{"id": "1"}]})
        mc = _mock_client(mock_resp)
        with patch.object(URAQdrantClient, "_get_client", AsyncMock(return_value=mc)):
            client = URAQdrantClient()
            result = await client.buscar_vectores("docs", [0.1], limite=5)
            assert result == {"result": [{"id": "1"}]}

    @pytest.mark.asyncio
    async def test_buscar_vectores_http_error(self) -> None:
        mock_resp = _http_resp(500, {})
        mc = _mock_client(mock_resp)
        with patch.object(URAQdrantClient, "_get_client", AsyncMock(return_value=mc)):
            client = URAQdrantClient()
            result = await client.buscar_vectores("docs", [0.1])
            assert result == {"result": []}

    @pytest.mark.asyncio
    async def test_buscar_vectores_network_error(self) -> None:
        mc = AsyncMock(spec=httpx.AsyncClient)
        mc.post = AsyncMock(side_effect=httpx.RequestError("net err", request=MagicMock()))
        mc.is_closed = False
        with patch.object(URAQdrantClient, "_get_client", AsyncMock(return_value=mc)):
            client = URAQdrantClient()
            result = await client.buscar_vectores("docs", [0.1])
            assert result == {"result": []}

    @pytest.mark.asyncio
    async def test_upsert_puntos_success(self) -> None:
        mc = _mock_client(_http_resp(200))
        with patch.object(URAQdrantClient, "_get_client", AsyncMock(return_value=mc)):
            client = URAQdrantClient()
            n = await client.upsert_puntos("docs", [{"id": 1, "vector": [0.1]}])
            assert n == 1

    @pytest.mark.asyncio
    async def test_upsert_puntos_server_error(self) -> None:
        mc = _mock_client(_http_resp(500))
        with patch.object(URAQdrantClient, "_get_client", AsyncMock(return_value=mc)):
            client = URAQdrantClient()
            n = await client.upsert_puntos("docs", [{"id": 1}])
            assert n == 0

    @pytest.mark.asyncio
    async def test_close_cleans_up(self) -> None:
        client = URAQdrantClient()
        mc = AsyncMock(spec=httpx.AsyncClient)
        mc.is_closed = False
        mc.aclose = AsyncMock()
        client._client = mc
        await client.close()
        mc.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self) -> None:
        client = URAQdrantClient()
        await client.close()

    @pytest.mark.asyncio
    async def test_asegurar_coleccion_hibrida_exists(self) -> None:
        mc = _mock_client(_http_resp(200))
        with patch.object(URAQdrantClient, "_get_client", AsyncMock(return_value=mc)):
            client = URAQdrantClient()
            assert await client.asegurar_coleccion_hibrida("test_col") is True
            mc.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_asegurar_coleccion_hibrida_creates(self) -> None:
        mc = AsyncMock(spec=httpx.AsyncClient)
        mc.get = AsyncMock(return_value=_http_resp(404))
        mc.put = AsyncMock(return_value=_http_resp(201))
        mc.is_closed = False
        with patch.object(URAQdrantClient, "_get_client", AsyncMock(return_value=mc)):
            client = URAQdrantClient()
            assert await client.asegurar_coleccion_hibrida("test_col") is True
            mc.put.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_buscar_hibrido_success(self) -> None:
        mc = _mock_client(_http_resp(200, {"result": [{"id": "d1", "score": 0.9}]}))
        with patch.object(URAQdrantClient, "_get_client", AsyncMock(return_value=mc)):
            client = URAQdrantClient()
            result = await client.buscar_hibrido("docs", "test query", [0.1] * 768, limite=5)
            assert len(result) == 1
            assert result[0]["id"] == "d1"

    @pytest.mark.asyncio
    async def test_buscar_hibrido_fallback_to_dense(self) -> None:
        mc = AsyncMock(spec=httpx.AsyncClient)
        resp_fail = _http_resp(500)
        resp_fallback = _http_resp(200, {"result": [{"id": "d2"}]})
        mc.post = AsyncMock(side_effect=[resp_fail, resp_fallback])
        mc.is_closed = False
        with patch.object(URAQdrantClient, "_get_client", AsyncMock(return_value=mc)):
            client = URAQdrantClient()
            result = await client.buscar_hibrido("docs", "fallback test", [0.5] * 768)
            assert len(result) == 1
            assert result[0]["id"] == "d2"
            assert mc.post.await_count == 2


# ===================================================================
# QdrantClient — REST methods (httpx raw, modo_rest=True)
# ===================================================================

def _rest_client() -> QdrantClient:
    config = MagicMock(spec=UraConfig)
    config.qdrant_host = "localhost"
    config.qdrant_port = 6333
    config.schema_version = "3.1"
    with patch("motor.core.qdrant_client.QdrantClient._conectar"):
        client = QdrantClient(config)
    client.disponible = True
    client._modo_rest = True
    client._cliente = None
    return client


class TestQdrantClientREST:
    # ── guardar_documento / guardar_documentos_batch ──

    @patch("motor.core.qdrant_client.httpx.put")
    @patch("motor.core.qdrant_client.QdrantClient.generar_embeddings_batch")
    def test_guardar_documento(self, mock_embed: MagicMock, mock_put: MagicMock) -> None:
        mock_embed.return_value = [[0.1, 0.2]]
        mock_put.return_value.status_code = 200
        client = _rest_client()
        result = client.guardar_documento("doc1", "texto de prueba", {"source": "test"})
        assert result is True
        mock_put.assert_called_once()
        body = mock_put.call_args[1]["json"]
        assert body["points"][0]["payload"]["id"] == "doc1"

    @patch("motor.core.qdrant_client.httpx.put")
    @patch("motor.core.qdrant_client.QdrantClient.generar_embeddings_batch")
    def test_guardar_documentos_batch(self, mock_embed: MagicMock, mock_put: MagicMock) -> None:
        mock_embed.return_value = [[0.1], [0.2]]
        mock_put.return_value.status_code = 200
        client = _rest_client()
        docs = [("d1", "text1", {"k": 1}), ("d2", "text2", {"k": 2})]
        n = client.guardar_documentos_batch(docs)
        assert n == 2

    @patch("motor.core.qdrant_client.httpx.put")
    @patch("motor.core.qdrant_client.QdrantClient.generar_embeddings_batch")
    def test_guardar_documento_server_error(self, mock_embed: MagicMock, mock_put: MagicMock) -> None:
        mock_embed.return_value = [[0.1]]
        mock_put.return_value.status_code = 500
        client = _rest_client()
        assert client.guardar_documento("doc1", "text") is False

    @patch("motor.core.qdrant_client.QdrantClient.generar_embeddings_batch")
    def test_guardar_documento_not_disponible(self, mock_embed: MagicMock) -> None:
        client = _rest_client()
        client.disponible = False
        assert client.guardar_documento("doc1", "text") is False
        mock_embed.assert_not_called()

    # ── buscar_por_similitud / _buscar_similitud_rest ──

    @patch("motor.core.qdrant_client.httpx.post")
    def test_buscar_similitud_rest_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "result": [{"id": 1, "payload": {"texto": "hi"}, "score": 0.9}]
        }
        client = _rest_client()
        results = client.buscar_por_similitud([0.1, 0.2], "docs", 5)
        assert len(results) == 1
        assert results[0]["payload"]["texto"] == "hi"
        assert results[0]["score"] == 0.9

    @patch("motor.core.qdrant_client.httpx.post")
    def test_buscar_similitud_rest_empty(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"result": []}
        client = _rest_client()
        results = client.buscar_por_similitud([0.1], "docs", 5)
        assert results == []

    @patch("motor.core.qdrant_client.httpx.post")
    def test_buscar_similitud_rest_exception(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = Exception("timeout")
        client = _rest_client()
        assert client.buscar_por_similitud([0.1], "docs") == []

    # ── buscar_documentos ──

    @patch("motor.core.qdrant_client.QdrantClient.buscar_por_similitud")
    @patch("motor.core.qdrant_client.QdrantClient.generar_embedding")
    def test_buscar_documentos(self, mock_embed: MagicMock, mock_search: MagicMock) -> None:
        mock_embed.return_value = [0.1, 0.2]
        mock_search.return_value = [{"payload": {"texto": "doc"}, "score": 1.0}]
        client = _rest_client()
        results = client.buscar_documentos("query")
        assert len(results) == 1
        mock_embed.assert_called_with("query")
        mock_search.assert_called_with([0.1, 0.2], COLECCION_DOCUMENTOS, 10)

    # ── eliminar_por_filtro ──

    @patch("motor.core.qdrant_client.httpx.post")
    def test_eliminar_por_filtro_rest_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        client = _rest_client()
        assert client.eliminar_por_filtro({"source": "x"}, "test_col") is True

    @patch("motor.core.qdrant_client.httpx.post")
    def test_eliminar_por_filtro_server_error(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 500
        client = _rest_client()
        assert client.eliminar_por_filtro({"source": "x"}, "test_col") is False

    def test_eliminar_por_filtro_not_disponible(self) -> None:
        client = _rest_client()
        client.disponible = False
        assert client.eliminar_por_filtro({"k": "v"}) is False

    # ── guardar_incidente / _guardar_rest ──

    @patch("motor.core.qdrant_client.httpx.put")
    def test_guardar_incidente_rest_success(self, mock_put: MagicMock) -> None:
        mock_put.return_value.status_code = 200
        client = _rest_client()
        incidente = {"ts": "2026-01-01T00:00:00", "tipo": "CRASH", "impacto_memoria": [0.5] * VECTOR_SIZE}
        assert client.guardar_incidente(incidente) is True
        url = mock_put.call_args[0][0]
        assert COLECCION_INCIDENTES in url

    @patch("motor.core.qdrant_client.httpx.put")
    def test_guardar_incidente_server_error(self, mock_put: MagicMock) -> None:
        mock_put.return_value.status_code = 500
        client = _rest_client()
        assert client.guardar_incidente({"ts": "now"}) is False

    def test_guardar_incidente_not_disponible(self) -> None:
        client = _rest_client()
        client.disponible = False
        assert client.guardar_incidente({"ts": "now"}) is False

    # ── buscar_incidentes / _buscar_rest ──

    @patch("motor.core.qdrant_client.httpx.post")
    def test_buscar_incidentes_rest_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "result": {"points": [{"payload": {"tipo": "CRASH"}}]}
        }
        client = _rest_client()
        results = client.buscar_incidentes(limit=5)
        assert len(results) == 1
        assert results[0]["tipo"] == "CRASH"

    @patch("motor.core.qdrant_client.httpx.post")
    def test_buscar_incidentes_rest_empty(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"result": {"points": []}}
        client = _rest_client()
        assert client.buscar_incidentes() == []

    @patch("motor.core.qdrant_client.httpx.post")
    def test_buscar_incidentes_rest_exception(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = Exception("timeout")
        client = _rest_client()
        assert client.buscar_incidentes() == []

    def test_buscar_incidentes_not_disponible(self) -> None:
        client = _rest_client()
        client.disponible = False
        assert client.buscar_incidentes() == []

    # ── guardar_documentos_batch: HTTP exception ──

    @patch("motor.core.qdrant_client.httpx.put")
    @patch("motor.core.qdrant_client.QdrantClient.generar_embeddings_batch")
    def test_guardar_documentos_batch_http_exception(
        self, mock_embed: MagicMock, mock_put: MagicMock
    ) -> None:
        mock_embed.return_value = [[0.1]]
        mock_put.side_effect = httpx.RequestError("net err", request=MagicMock())
        client = _rest_client()
        n = client._guardar_documentos_rest([{"id": 1}], "docs")
        assert n == 0
