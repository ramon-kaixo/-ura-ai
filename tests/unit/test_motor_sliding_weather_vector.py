"""Tests para motor/scanner/sliding_window.py, motor/assistant/tool_plugins/weather.py y motor/intelligence/retrieval/vector.py."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from motor.intelligence.retrieval.vector import VectorRetriever
from motor.scanner.sliding_window import SlidingWindow


class TestSlidingWindow:
    def test_menos_de_3_muestras(self) -> None:
        w = SlidingWindow(maxlen=3)
        assert w.add_and_check(SimpleNamespace(servicios={"a": "active"})) == []
        assert w.add_and_check(SimpleNamespace(servicios={"a": "active"})) == []
        assert len(w.add_and_check(SimpleNamespace(servicios={"a": "active"}))) == 0  # sin flapping

    def test_detecta_flapping(self) -> None:
        w = SlidingWindow(maxlen=3)
        w.add_and_check(SimpleNamespace(servicios={"svc1": "active"}))
        w.add_and_check(SimpleNamespace(servicios={"svc1": "active"}))
        flapping = w.add_and_check(SimpleNamespace(servicios={"svc1": "failed"}))
        assert len(flapping) == 1
        assert flapping[0]["servicio"] == "svc1"
        assert set(flapping[0]["cambios"]) == {"active", "failed"}

    def test_buffer_limitado(self) -> None:
        w = SlidingWindow(maxlen=3)
        for i in range(6):
            w.add_and_check(SimpleNamespace(servicios={"s": f"e{i}"}))
        assert len(w._buffer) == 3  # deque limita

    def test_sin_servicios_attr(self) -> None:
        w = SlidingWindow(maxlen=3)
        w.add_and_check(object())
        w.add_and_check(object())
        assert w.add_and_check(object()) == []

    def test_varios_servicios(self) -> None:
        w = SlidingWindow(maxlen=3)
        w.add_and_check(SimpleNamespace(servicios={"a": "x", "b": "y"}))
        w.add_and_check(SimpleNamespace(servicios={"a": "x", "b": "z"}))
        flapping = w.add_and_check(SimpleNamespace(servicios={"a": "x", "b": "y"}))
        assert len(flapping) == 1
        assert flapping[0]["servicio"] == "b"


class TestWeatherPlugin:
    @pytest.fixture
    def plugin(self):
        from motor.assistant.tool_plugins.weather import WeatherPlugin

        return WeatherPlugin()

    def test_meta(self, plugin) -> None:
        assert plugin.name == "weather"
        assert "clima" in plugin.keywords

    @pytest.mark.asyncio
    async def test_sin_location(self, plugin) -> None:
        r = await plugin.execute({})
        assert r.success is False
        assert "Ciudad no especificada" in r.error

    @pytest.mark.asyncio
    async def test_ok(self, plugin, monkeypatch) -> None:
        resp = mock.Mock()
        resp.status_code = 200
        resp.text = "Sunny +25C"
        monkeypatch.setattr("motor.assistant.tool_plugins.weather.httpx.get", mock.AsyncMock(return_value=resp))
        r = await plugin.execute({"location": "madrid"})
        assert r.success is True
        assert "madrid" in r.output

    @pytest.mark.asyncio
    async def test_error_http(self, plugin, monkeypatch) -> None:
        resp = mock.Mock()
        resp.status_code = 500
        resp.text = ""
        monkeypatch.setattr("motor.assistant.tool_plugins.weather.httpx.get", mock.AsyncMock(return_value=resp))
        r = await plugin.execute({"location": "x"})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_excepcion(self, plugin, monkeypatch) -> None:
        monkeypatch.setattr("motor.assistant.tool_plugins.weather.httpx.get", mock.AsyncMock(side_effect=OSError("net")))
        r = await plugin.execute({"location": "x"})
        assert r.success is False
        assert "net" in r.error


class TestVectorRetriever:
    def test_sin_cliente_retorna_vacio(self) -> None:
        qc = mock.Mock()
        qc._cliente = None
        qc.generar_embedding.return_value = [0.1, 0.2]
        r = VectorRetriever(qc)
        assert r.search("query") == []

    def test_search_ok(self) -> None:
        qc = mock.Mock()
        client = mock.Mock()
        hit = mock.Mock()
        hit.payload = {"source": "doc1", "texto": "contenido"}
        hit.score = 0.9
        hit.id = "id1"
        client.query_points.return_value = SimpleNamespace(points=[hit])
        qc._cliente = client
        qc.generar_embedding.return_value = [0.1, 0.2]
        r = VectorRetriever(qc)
        results = r.search("query", k=5)
        assert len(results) == 1
        assert results[0]["doc_id"] == "doc1"
        assert results[0]["score"] == 0.9
        assert results[0]["source"] == "vector"
        assert results[0]["rank"] == 0
        client.query_points.assert_called_once_with(collection_name="ura_docs_semantic", query=[0.1, 0.2], limit=5, with_payload=True)

    def test_sin_payload_id_fallback(self) -> None:
        qc = mock.Mock()
        client = mock.Mock()
        hit = mock.Mock()
        hit.payload = None
        hit.score = 0.5
        hit.id = "idX"
        client.query_points.return_value = SimpleNamespace(points=[hit])
        qc._cliente = client
        qc.generar_embedding.return_value = [0.1]
        r = VectorRetriever(qc)
        results = r.search("q")
        assert results[0]["doc_id"] == "idX"

    def test_sin_hits(self) -> None:
        qc = mock.Mock()
        client = mock.Mock()
        client.query_points.return_value = SimpleNamespace(points=[])
        qc._cliente = client
        qc.generar_embedding.return_value = [0.1]
        r = VectorRetriever(qc)
        assert r.search("q") == []

    def test_collection_personalizada(self) -> None:
        qc = mock.Mock()
        qc._cliente = mock.Mock()
        qc._cliente.query_points.return_value = SimpleNamespace(points=[])
        qc.generar_embedding.return_value = [0.1]
        r = VectorRetriever(qc, collection="mi_col")
        r.search("q")
        assert qc._cliente.query_points.call_args.kwargs["collection_name"] == "mi_col"
