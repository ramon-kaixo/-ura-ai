"""Tests para motor/core/qdrant_rest.py."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from motor.core.qdrant_rest import (
    buscar_similitud_rest,
    eliminar_por_filtro_rest,
    guardar_documentos_rest,
    guardar_rest,
)


@pytest.fixture
def config() -> SimpleNamespace:
    return SimpleNamespace(qdrant_host="127.0.0.1", qdrant_port=6333)


class FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


class TestGuardarRest:
    def test_ok(self, config, monkeypatch) -> None:
        resp = FakeResp(201)
        put = mock.Mock(return_value=resp)
        monkeypatch.setattr("motor.core.qdrant_rest.httpx.put", put)
        incidente = {"timestamp_inicio": "2026-01-01T00:00:00"}
        build = mock.Mock(return_value={"timestamp_inicio": "2026-01-01T00:00:00", "impacto_memoria": [0.1]})
        assert guardar_rest(config, incidente, build) is True
        args = put.call_args
        assert args.args[0] == "http://127.0.0.1:6333/collections/incidentes/points"
        assert "points" in args.kwargs["json"]

    def test_error(self, config, monkeypatch) -> None:
        monkeypatch.setattr("motor.core.qdrant_rest.httpx.put", mock.Mock(side_effect=OSError("net")))
        build = mock.Mock(return_value={"timestamp_inicio": "t", "impacto_memoria": [0.1]})
        assert guardar_rest(config, {}, build) is False


class TestGuardarDocumentosRest:
    def test_ok(self, config, monkeypatch) -> None:
        resp = FakeResp(200)
        put = mock.Mock(return_value=resp)
        monkeypatch.setattr("motor.core.qdrant_rest.httpx.put", put)
        assert guardar_documentos_rest(config, [{"id": 1}, {"id": 2}], "docs") == 2

    def test_status_no_2xx(self, config, monkeypatch) -> None:
        resp = FakeResp(500)
        monkeypatch.setattr("motor.core.qdrant_rest.httpx.put", mock.Mock(return_value=resp))
        assert guardar_documentos_rest(config, [{"id": 1}], "docs") == 0

    def test_error(self, config, monkeypatch) -> None:
        monkeypatch.setattr("motor.core.qdrant_rest.httpx.put", mock.Mock(side_effect=OSError("net")))
        assert guardar_documentos_rest(config, [{"id": 1}], "docs") == 0


class TestBuscarSimilitudRest:
    def test_ok(self, config, monkeypatch) -> None:
        resp = FakeResp(200, {"result": [{"payload": {"a": 1}, "score": 0.9}, {"payload": {"b": 2}, "score": 0.5}]})
        post = mock.Mock(return_value=resp)
        monkeypatch.setattr("motor.core.qdrant_rest.httpx.post", post)
        out = buscar_similitud_rest(config, [0.1, 0.2], "docs", 5)
        assert len(out) == 2
        assert out[0]["score"] == 0.9
        args = post.call_args.kwargs["json"]
        assert args["limit"] == 5

    def test_status_error(self, config, monkeypatch) -> None:
        resp = FakeResp(500)
        monkeypatch.setattr("motor.core.qdrant_rest.httpx.post", mock.Mock(return_value=resp))
        assert buscar_similitud_rest(config, [0.1], "docs", 5) == []

    def test_error(self, config, monkeypatch) -> None:
        monkeypatch.setattr("motor.core.qdrant_rest.httpx.post", mock.Mock(side_effect=OSError("net")))
        assert buscar_similitud_rest(config, [0.1], "docs", 5) == []


class TestEliminarPorFiltroRest:
    def test_ok(self, config, monkeypatch) -> None:
        resp = FakeResp(200)
        post = mock.Mock(return_value=resp)
        monkeypatch.setattr("motor.core.qdrant_rest.httpx.post", post)
        assert eliminar_por_filtro_rest(config, {"fuente": "x"}, "docs") is True
        filtro = post.call_args.kwargs["json"]["filter"]["must"]
        assert filtro == [{"key": "fuente", "match": {"value": "x"}}]

    def test_error(self, config, monkeypatch) -> None:
        monkeypatch.setattr("motor.core.qdrant_rest.httpx.post", mock.Mock(side_effect=OSError("net")))
        assert eliminar_por_filtro_rest(config, {"a": 1}, "docs") is False
