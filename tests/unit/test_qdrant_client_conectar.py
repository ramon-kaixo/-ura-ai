"""Tests cobertura motor qdrant_client — conectar/colecciones/embeddings/guardar (split)."""
from __future__ import annotations

from _qdrant_helpers import (  # noqa: F401
    COLECCION_DOCUMENTOS,
    COLECCION_INCIDENTES,
    COLECCION_TRANSACCIONES,
    VECTOR_SIZE_EMBEDDING,
    AsyncMock,
    FakeQC,
    FakeResp,
    MagicMock,
    QdrantClient,
    asyncio,
    client,
    hashlib,
    json,
    make_config,
    native_modules,
    patch,
    pytest,
    qc_mod,
    sys,
)


class TestConectar:
    @patch("motor.core.qdrant_client.DegradedMode")
    def test_conectar_nativo_ok(self, mock_dm: MagicMock, native_modules: dict) -> None:  # noqa: F811
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
    def test_conectar_rest_fallback(self, mock_get: MagicMock, mock_put: MagicMock, mock_dm: MagicMock, native_modules: dict) -> None:  # noqa: F811
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
    def test_conectar_degradado(self, mock_get: MagicMock, mock_dm: MagicMock, native_modules: dict) -> None:  # noqa: F811
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
    def test_conectar_rest_status_500(self, mock_get: MagicMock, mock_dm: MagicMock, native_modules: dict) -> None:  # noqa: F811
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
    def test_rest_creates_on_404(self, client: QdrantClient, metodo: str, coleccion: str) -> None:  # noqa: F811
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "get") as mget, patch.object(qc_mod.httpx, "put") as mput:
            mget.return_value = FakeResp(404)
            mput.return_value = FakeResp(201)
            getattr(client, metodo)()
        assert mget.called
        assert mput.called
        assert coleccion in mput.call_args[0][0]

    @pytest.mark.parametrize("metodo", ["_asegurar_coleccion", "_asegurar_coleccion_documentos"])
    def test_rest_200_noop(self, client: QdrantClient, metodo: str) -> None:  # noqa: F811
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "get") as mget, patch.object(qc_mod.httpx, "put") as mput:
            mget.return_value = FakeResp(200)
            getattr(client, metodo)()
        assert mput.call_count == 0

    def test_rest_put_non_2xx(self, client: QdrantClient) -> None:  # noqa: F811
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "get") as mget, patch.object(qc_mod.httpx, "put") as mput:
            mget.return_value = FakeResp(404)
            mput.return_value = FakeResp(500)
            client._asegurar_coleccion()
        assert mput.called

    def test_rest_get_error(self, client: QdrantClient) -> None:  # noqa: F811
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
    def test_native_creates(self, client: QdrantClient, native_modules: dict, metodo: str, coleccion: str) -> None:  # noqa: F811
        client._modo_rest = False
        qc = FakeQC()
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            getattr(client, metodo)()
        assert qc.created == [coleccion]
        assert qc.created[0] == coleccion

    @pytest.mark.parametrize("metodo", ["_asegurar_coleccion", "_asegurar_coleccion_documentos"])
    def test_native_exists(self, client: QdrantClient, native_modules: dict, metodo: str) -> None:  # noqa: F811
        client._modo_rest = False
        qc = FakeQC()
        qc.existing = [COLECCION_INCIDENTES, COLECCION_DOCUMENTOS, COLECCION_TRANSACCIONES]
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            getattr(client, metodo)()
        assert qc.created == []

    def test_native_other_error(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
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
    def test_native_other_error_restantes(self, client: QdrantClient, native_modules: dict, metodo: str) -> None:  # noqa: F811
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
    def test_ok(self, client: QdrantClient) -> None:  # noqa: F811
        with patch.object(client, "generar_embeddings_batch_async", new=AsyncMock(return_value=[[0.1, 0.2]])):
            out = asyncio.run(client.generar_embedding_async("texto"))
        assert out == [0.1, 0.2]

    def test_zero_vector(self, client: QdrantClient) -> None:  # noqa: F811
        with patch.object(client, "generar_embeddings_batch_async", new=AsyncMock(return_value=[[0.0, 0.0]])):
            out = asyncio.run(client.generar_embedding_async("texto"))
        assert out == [0.0] * VECTOR_SIZE_EMBEDDING

    def test_empty_result(self, client: QdrantClient) -> None:  # noqa: F811
        with patch.object(client, "generar_embeddings_batch_async", new=AsyncMock(return_value=[])):
            out = asyncio.run(client.generar_embedding_async("texto"))
        assert out == [0.0] * VECTOR_SIZE_EMBEDDING

    def test_batch_async_delega_en_llm(self, client: QdrantClient) -> None:  # noqa: F811
        with patch("motor.core.qdrant_client.llm_embed_async", new=AsyncMock(return_value=[[0.1]])) as m:
            out = asyncio.run(client.generar_embeddings_batch_async(["x"]))
        m.assert_awaited_with(["x"], model="nomic-embed-text")
        assert out == [[0.1]]


# ===================================================================
# Guardar documentos
# ===================================================================


class TestGuardarDocumentos:
    def test_no_disponible(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = False
        assert client._guardar_documentos([("a", "texto", {})]) == 0

    def test_empty_docs(self, client: QdrantClient) -> None:  # noqa: F811
        assert client._guardar_documentos([]) == 0

    def test_rest_ok(self, client: QdrantClient) -> None:  # noqa: F811
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

    def test_rest_500(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(500)
            assert client._guardar_documentos([("a", "t", {})]) == 0

    def test_rest_error(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.object(qc_mod.httpx, "put") as mput:
            mput.side_effect = OSError("net")
            assert client._guardar_documentos([("a", "t", {})]) == 0

    def test_native_ok(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
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

    def test_native_sin_cliente(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        client._cliente = None
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]):
            assert client._guardar_documentos([("a", "t", {})]) == 0

    def test_native_error(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.fail_upsert = True
        client._cliente = qc
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.dict(sys.modules, native_modules):
            assert client._guardar_documentos([("a", "t", {})]) == 0

    def test_doc_id_vacio_usa_texto(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(200)
            client._guardar_documentos([("", "texto unico", {})])
        pid = mput.call_args[1]["json"]["points"][0]["id"]
        expected = int(hashlib.sha256(b"texto unico").hexdigest()[:15], 16) % (2**63)
        assert pid == expected

    def test_pid_determinista(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch("motor.core.qdrant_client.llm_embed", return_value=[[0.1]]), patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(200)
            client._guardar_documentos([("doc-1", "texto", {})])
        pid = mput.call_args[1]["json"]["points"][0]["id"]
        expected = int(hashlib.sha256(b"doc-1").hexdigest()[:15], 16) % (2**63)
        assert pid == expected

    def test_guardar_documento(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        with patch.object(client, "_guardar_documentos", return_value=1) as m:
            assert client.guardar_documento("d1", "texto", {"a": 1}) is True
        m.assert_called_with([("d1", "texto", {"a": 1})], COLECCION_DOCUMENTOS)

    def test_guardar_documento_false(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        with patch.object(client, "_guardar_documentos", return_value=0):
            assert client.guardar_documento("d1", "texto") is False

    def test_guardar_documento_metadata_none(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        with patch.object(client, "_guardar_documentos", return_value=1) as m:
            client.guardar_documento("d1", "texto", None)
        m.assert_called_with([("d1", "texto", {})], COLECCION_DOCUMENTOS)

    def test_guardar_documentos_batch(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        docs = [("a", "t1", {}), ("b", "t2", {})]
        with patch.object(client, "_guardar_documentos", return_value=2) as m:
            assert client.guardar_documentos_batch(docs, "otra") == 2
        m.assert_called_with(docs, "otra")


# ===================================================================
# Buscar por similitud
# ===================================================================

