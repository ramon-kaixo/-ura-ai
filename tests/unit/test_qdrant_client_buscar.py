"""Tests cobertura motor qdrant_client — buscar/eliminar/incidentes (split)."""
from __future__ import annotations

from _qdrant_helpers import (  # noqa: F401
    COLECCION_DOCUMENTOS,
    COLECCION_INCIDENTES,
    FakeQC,
    FakeResp,
    QdrantClient,
    SimpleNamespace,
    client,
    json,
    native_modules,
    patch,
    qc_mod,
    sys,
)


class TestBuscarPorSimilitud:
    def test_no_disponible(self, client: QdrantClient) -> None:  # noqa: F811
        assert client.buscar_por_similitud([0.1]) == []

    def test_rest_ok(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.return_value = FakeResp(200, {"result": [{"payload": {"a": 1}, "score": 0.9}]})
            out = client.buscar_por_similitud([0.1, 0.2], limit=3)
        assert out == [{"payload": {"a": 1}, "score": 0.9}]
        payload = mpost.call_args[1]["json"]
        assert payload["limit"] == 3
        assert payload["vector"] == [0.1, 0.2]

    def test_rest_no_200(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.return_value = FakeResp(500)
            assert client.buscar_por_similitud([0.1]) == []

    def test_rest_error(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.side_effect = OSError("net")
            assert client.buscar_por_similitud([0.1]) == []

    def test_native_ok(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
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

    def test_native_points_none(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.query_result = SimpleNamespace(points=None)
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.buscar_por_similitud([0.1]) == []

    def test_native_sin_cliente(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        client._cliente = None
        assert client.buscar_por_similitud([0.1]) == []

    def test_native_error(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.fail_query = True
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.buscar_por_similitud([0.1]) == []

    def test_buscar_documentos(self, client: QdrantClient) -> None:  # noqa: F811
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
    def test_no_disponible(self, client: QdrantClient) -> None:  # noqa: F811
        assert client.eliminar_por_filtro({"a": 1}) is False

    def test_rest_dispatch(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(client, "_eliminar_por_filtro_rest", return_value=True) as m:
            assert client.eliminar_por_filtro({"a": 1}) is True
        m.assert_called_with({"a": 1}, COLECCION_DOCUMENTOS)

    def test_native_sin_cliente(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        client._cliente = None
        assert client.eliminar_por_filtro({"a": 1}) is False

    def test_native_ok(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
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

    def test_native_error(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.fail_delete = True
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.eliminar_por_filtro({"a": 1}) is False

    def test_rest_error(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "post") as mpost:
            mpost.side_effect = OSError("net")
            assert client._eliminar_por_filtro_rest({"a": 1}, "c") is False


# ===================================================================
# Incidentes
# ===================================================================


class TestGuardarIncidente:
    def test_no_disponible(self, client: QdrantClient) -> None:  # noqa: F811
        assert client.guardar_incidente({}) is False

    def test_rest_dispatch(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(client, "_guardar_rest", return_value=True) as m:
            assert client.guardar_incidente({"ts": "t"}) is True
        m.assert_called_with({"ts": "t"})

    def test_native_sin_cliente(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        client._cliente = None
        assert client.guardar_incidente({}) is False

    def test_native_ok(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
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

    def test_native_error(self, client: QdrantClient, native_modules: dict) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = False
        qc = FakeQC()
        qc.fail_upsert = True
        client._cliente = qc
        with patch.dict(sys.modules, native_modules):
            assert client.guardar_incidente({}) is False



class TestGuardarRest:
    def test_ok(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(201)
            assert client._guardar_rest({"ts": "2026-01-01T00:00:00"}) is True
        point = mput.call_args[1]["json"]["points"][0]
        assert point["vector"] == [0.0] * 7
        assert point["payload"]["tipo_incidencia"] == "Unknown"

    def test_no_2xx(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "put") as mput:
            mput.return_value = FakeResp(500)
            assert client._guardar_rest({}) is False

    def test_error(self, client: QdrantClient) -> None:  # noqa: F811
        client.disponible = True
        client._modo_rest = True
        with patch.object(qc_mod.httpx, "put") as mput:
            mput.side_effect = OSError("net")
            assert client._guardar_rest({}) is False


