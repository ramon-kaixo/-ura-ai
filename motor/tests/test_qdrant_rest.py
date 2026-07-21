"""Tests para qdrant_rest.py — funciones REST de Qdrant.

Verifica que las funciones extraidas mantienen la misma logica
que cuando estaban inline en qdrant_client.py.
Usa respuestas simuladas (no requiere Qdrant real).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from motor.core import qdrant_rest


class MockResponse:
    def __init__(self, status_code: int, json_data: dict | None = None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class MockConfig:
    qdrant_host = "127.0.0.1"
    qdrant_port = 6333


def test_guardar_rest_exitoso():
    config = MockConfig()
    incidente = {"ts": "2026-01-01T00:00:00Z", "tipo": "test", "vector": [0.1, 0.2, 0.3]}

    def build_payload(d):
        return {
            "timestamp_inicio": d.get("ts", ""),
            "impacto_memoria": d.get("vector", [0.0] * 7),
            "tipo_incidencia": d.get("tipo", "Unknown"),
        }

    with patch("motor.core.qdrant_rest.httpx.put", return_value=MockResponse(200)) as mock_put:
        result = qdrant_rest.guardar_rest(config, incidente, build_payload)
        assert result is True
        mock_put.assert_called_once()
        url = mock_put.call_args[0][0]
        assert "127.0.0.1:6333" in url
        assert "incidentes" in url


def test_guardar_rest_fallo():
    config = MockConfig()

    def build_payload(d):
        return {"timestamp_inicio": "", "impacto_memoria": [0.0] * 7, "tipo_incidencia": "test"}

    with patch("motor.core.qdrant_rest.httpx.put", return_value=MockResponse(500)) as mock_put:
        result = qdrant_rest.guardar_rest(config, {"ts": ""}, build_payload)
        assert result is False
        mock_put.assert_called_once()


def test_guardar_documentos_rest():
    config = MockConfig()
    puntos = [{"id": 1, "vector": [0.1], "payload": {}}]

    with patch("motor.core.qdrant_rest.httpx.put", return_value=MockResponse(201)) as mock_put:
        result = qdrant_rest.guardar_documentos_rest(config, puntos, "test_collection")
        assert result == 1
        mock_put.assert_called_once()
        assert "test_collection" in mock_put.call_args[0][0]


def test_buscar_similitud_rest():
    config = MockConfig()
    mock_json = {"result": [{"payload": {"text": "test"}, "score": 0.95}]}

    with patch("motor.core.qdrant_rest.httpx.post", return_value=MockResponse(200, mock_json)):
        results = qdrant_rest.buscar_similitud_rest(config, [0.1, 0.2], "docs", 5)
        assert len(results) == 1
        assert results[0]["score"] == 0.95
        assert results[0]["payload"]["text"] == "test"


def test_buscar_similitud_rest_vacio():
    config = MockConfig()
    with patch("motor.core.qdrant_rest.httpx.post", return_value=MockResponse(500)):
        results = qdrant_rest.buscar_similitud_rest(config, [0.1], "docs", 5)
        assert results == []


def test_eliminar_por_filtro_rest():
    config = MockConfig()
    filtro = {"source": "test"}

    with patch("motor.core.qdrant_rest.httpx.post", return_value=MockResponse(200)) as mock_post:
        result = qdrant_rest.eliminar_por_filtro_rest(config, filtro, "docs")
        assert result is True
        mock_post.assert_called_once()
        body = mock_post.call_args[1]["json"]
        assert body["filter"]["must"][0]["key"] == "source"


def test_eliminar_por_filtro_rest_fallo():
    config = MockConfig()
    with patch("motor.core.qdrant_rest.httpx.post", return_value=MockResponse(500)):
        result = qdrant_rest.eliminar_por_filtro_rest(config, {}, "docs")
        assert result is False
