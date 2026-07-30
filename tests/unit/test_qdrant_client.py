"""Unit tests para qdrant_client.py — funciones puras + lógica de negocio.

Mock permitido: DegradedMode (singleton), asyncio.get_running_loop(), llm_embed.
Mock NO permitido: funciones internas de qdrant_client.py.
"""
from __future__ import annotations

import asyncio
import hashlib
import threading
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from motor.core.qdrant_client import (
    COLECCION_INCIDENTES,
    VECTOR_SIZE,
    QdrantClient,
    UraConfig,
    generar_sparse_vector,
)


# ===================================================================
# Grupo A — generar_sparse_vector (pura, 0 mock)
# ===================================================================

class TestGenerarSparseVector:
    def test_empty_string(self) -> None:
        result = generar_sparse_vector("")
        assert result == {"indices": [], "values": []}

    def test_basic_tf(self) -> None:
        result = generar_sparse_vector("hola mundo hola")
        indices = result["indices"]
        values = result["values"]
        assert len(indices) == 2
        assert len(values) == 2
        v = {indices[i]: values[i] for i in range(2)}
        assert set(v.values()) == {2 / 3, 1 / 3}

    def test_max_tokens_truncation(self) -> None:
        tokens = "palabra " * 100
        result = generar_sparse_vector(tokens, max_tokens=5)
        assert len(result["indices"]) <= 5

    def test_special_chars_ignored(self) -> None:
        result = generar_sparse_vector("¡hola! mundo... test")
        v = dict(zip(result["indices"], result["values"], strict=False))
        assert len(v) == 3  # hola, mundo, test
        assert abs(sum(v.values()) - 1.0) < 1e-9

    def test_indices_positive(self) -> None:
        result = generar_sparse_vector("a b c")
        assert all(i >= 0 for i in result["indices"])

    def test_repeated_word_single_token(self) -> None:
        result = generar_sparse_vector("si si si si si")
        assert len(result["indices"]) == 1
        assert result["values"] == [1.0]

    def test_deterministic(self) -> None:
        r1 = generar_sparse_vector("hola mundo")
        r2 = generar_sparse_vector("hola mundo")
        assert r1 == r2


# ===================================================================
# Grupo B — _build_payload (pura, 0 mock)
# ===================================================================

class TestBuildPayload:
    def _make_client(self) -> QdrantClient:
        config = MagicMock(spec=UraConfig)
        config.qdrant_host = "localhost"
        config.qdrant_port = 6333
        config.schema_version = "3.1"
        with patch("motor.core.qdrant_client.QdrantClient._conectar"):
            return QdrantClient(config)

    def test_minimal(self) -> None:
        client = self._make_client()
        payload = client._build_payload({"ts": "2026-01-01T00:00:00"})
        assert payload["timestamp_inicio"] == "2026-01-01T00:00:00"
        assert payload["timestamp_resolucion"] == ""
        assert payload["tipo_incidencia"] == "Unknown"
        assert payload["subtipo"] == ""
        assert payload["resumen"] == ""
        assert payload["impacto_memoria"] == [0.0] * VECTOR_SIZE
        assert payload["schema_version"] == "3.1"
        assert payload["hw_ok"] is True
        assert payload["exit_code"] == -1
        assert payload["signal"] == 0
        assert payload["oom_killed"] is False
        assert payload["segfault"] is False
        assert payload["origin_node"] == "ASUS"

    def test_full(self) -> None:
        client = self._make_client()
        incidente = {
            "ts": "2026-06-01T12:00:00",
            "ts_resolucion": "2026-06-01T13:00:00",
            "tipo": "CRASH",
            "subtipo": "OOM",
            "resumen": "Out of memory",
            "impacto_memoria": [0.5] * VECTOR_SIZE,
            "hw_ok": False,
            "hw_issues": ["RAM"],
            "affected_resources": {"gpu": 0},
            "cleanup_cmd": "kill -9",
            "pre_state": {"memory": 95},
            "trace": "trace123",
            "origin_node": "HETZNER",
            "dependency_chain": ["A", "B"],
            "exit_code": 137,
            "signal": 9,
            "oom_killed": True,
            "segfault": False,
        }
        payload = client._build_payload(incidente)
        assert payload["timestamp_inicio"] == "2026-06-01T12:00:00"
        assert payload["timestamp_resolucion"] == "2026-06-01T13:00:00"
        assert payload["tipo_incidencia"] == "CRASH"
        assert payload["subtipo"] == "OOM"
        assert payload["resumen"] == "Out of memory"
        assert payload["hw_ok"] is False
        assert payload["hw_issues"] == ["RAM"]
        assert payload["affected_resources"] == {"gpu": 0}
        assert payload["cleanup_cmd"] == "kill -9"
        assert payload["trace"] == "trace123"
        assert payload["origin_node"] == "HETZNER"
        assert payload["exit_code"] == 137
        assert payload["signal"] == 9
        assert payload["oom_killed"] is True

    def test_empty_dict_defaults(self) -> None:
        client = self._make_client()
        payload = client._build_payload({})
        assert payload["tipo_incidencia"] == "Unknown"
        assert payload["impacto_memoria"] == [0.0] * VECTOR_SIZE
        assert payload["hw_ok"] is True
        assert payload["exit_code"] == -1


# ===================================================================
# Grupo C — health() logic (DegradedMode mock)
# ===================================================================

class TestHealthLogic:
    def _make_client(self) -> QdrantClient:
        config = MagicMock(spec=UraConfig)
        config.qdrant_host = "localhost"
        config.qdrant_port = 6333
        config.schema_version = "3.1"
        with patch("motor.core.qdrant_client.QdrantClient._conectar"):
            client = QdrantClient(config)
        client.disponible = True
        client._modo_rest = False
        client._cliente = MagicMock()
        return client

    @patch("motor.core.qdrant_client.DegradedMode")
    def test_disponible_false(self, MockDM: MagicMock) -> None:
        client = self._make_client()
        dm_instance = MockDM.instancia.return_value
        client.disponible = False
        assert client.health() is False
        dm_instance.mark_degraded.assert_called_with("qdrant")

    @patch("motor.core.qdrant_client.DegradedMode")
    def test_modo_rest_true(self, MockDM: MagicMock) -> None:
        client = self._make_client()
        dm_instance = MockDM.instancia.return_value
        client._modo_rest = True
        assert client.health() is True
        dm_instance.mark_healthy.assert_called_with("qdrant")

    @patch("motor.core.qdrant_client.DegradedMode")
    def test_cliente_none(self, MockDM: MagicMock) -> None:
        client = self._make_client()
        dm_instance = MockDM.instancia.return_value
        client._cliente = None
        assert client.health() is False
        dm_instance.mark_degraded.assert_called_with("qdrant")

    @patch("motor.core.qdrant_client.DegradedMode")
    def test_cliente_exception(self, MockDM: MagicMock) -> None:
        client = self._make_client()
        dm_instance = MockDM.instancia.return_value
        client._cliente.get_collections.side_effect = Exception("connection lost")
        assert client.health() is False
        assert client.disponible is False
        dm_instance.mark_degraded.assert_called_with("qdrant")

    @patch("motor.core.qdrant_client.DegradedMode")
    def test_cliente_ok(self, MockDM: MagicMock) -> None:
        client = self._make_client()
        dm_instance = MockDM.instancia.return_value
        assert client.health() is True
        client._cliente.get_collections.assert_called_once()
        dm_instance.mark_healthy.assert_called_with("qdrant")

    @patch("motor.core.qdrant_client.DegradedMode")
    def test_disponible_false_no_http(self, MockDM: MagicMock) -> None:
        """Si disponible=False, health retorna False sin tocar cliente."""
        client = self._make_client()
        client.disponible = False
        client._cliente = None
        assert client.health() is False


# ===================================================================
# Grupo D — _eliminar_por_filtro filter construction (0 mock)
# ===================================================================

class TestEliminarFilter:
    def _make_client(self) -> QdrantClient:
        config = MagicMock(spec=UraConfig)
        config.qdrant_host = "localhost"
        config.qdrant_port = 6333
        with patch("motor.core.qdrant_client.QdrantClient._conectar"):
            return QdrantClient(config)

    @patch("motor.core.qdrant_client.httpx.post")
    def test_single_filter_str_value(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {}
        client = self._make_client()
        client.disponible = True
        client._modo_rest = True
        result = client._eliminar_por_filtro_rest({"source": "/path/to/file"}, "test_collection")
        assert result is True
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["filter"]["must"] == [{"key": "source", "match": {"value": "/path/to/file"}}]

    @patch("motor.core.qdrant_client.httpx.post")
    def test_multi_filter(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {}
        client = self._make_client()
        client.disponible = True
        client._modo_rest = True
        client._eliminar_por_filtro_rest({"a": 1, "b": "x"}, "c")
        payload = mock_post.call_args[1]["json"]
        assert len(payload["filter"]["must"]) == 2

    @patch("motor.core.qdrant_client.httpx.post")
    def test_empty_filter(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {}
        client = self._make_client()
        client.disponible = True
        client._modo_rest = True
        client._eliminar_por_filtro_rest({}, "c")
        payload = mock_post.call_args[1]["json"]
        assert payload["filter"]["must"] == []

    @patch("motor.core.qdrant_client.httpx.post")
    def test_server_error_returns_false(self, mock_post: MagicMock) -> None:
        mock_post.return_value.status_code = 500
        client = self._make_client()
        client.disponible = True
        client._modo_rest = True
        assert client._eliminar_por_filtro_rest({"k": "v"}, "c") is False


# ===================================================================
# Grupo E — generar_embedding sync/async wrapper
# ===================================================================

class TestGenerarEmbeddingWrapper:
    def _make_client(self) -> QdrantClient:
        config = MagicMock(spec=UraConfig)
        config.qdrant_host = "localhost"
        config.qdrant_port = 6333
        config.schema_version = "3.1"
        with patch("motor.core.qdrant_client.QdrantClient._conectar"):
            return QdrantClient(config)

    @patch("motor.core.qdrant_client.asyncio.get_running_loop")
    @patch("motor.core.qdrant_client.QdrantClient.generar_embedding_async")
    def test_no_loop_calls_asyncio_run(
        self, mock_async: MagicMock, mock_loop: MagicMock
    ) -> None:
        mock_loop.side_effect = RuntimeError("no loop")
        mock_async.return_value = [0.1, 0.2]
        client = self._make_client()
        result = client.generar_embedding("test")
        assert result == [0.1, 0.2]

    @patch("motor.core.qdrant_client.ThreadPoolExecutor")
    @patch("motor.core.qdrant_client.asyncio.get_running_loop")
    @patch("motor.core.qdrant_client.QdrantClient.generar_embedding_async")
    def test_with_loop_uses_executor(
        self, mock_async: MagicMock, mock_loop: MagicMock, mock_executor: MagicMock
    ) -> None:
        mock_loop.return_value = MagicMock()
        mock_async.return_value = [0.3, 0.4]
        future = MagicMock()
        future.result.return_value = [0.3, 0.4]
        executor_instance = MagicMock()
        executor_instance.submit.return_value = future
        mock_executor.return_value.__enter__.return_value = executor_instance

        client = self._make_client()
        result = client.generar_embedding("test")
        assert result == [0.3, 0.4]
        executor_instance.submit.assert_called_once()

    @patch("motor.core.qdrant_client.llm_embed")
    def test_generar_embeddings_batch(self, mock_embed: MagicMock) -> None:
        mock_embed.return_value = [[0.5, 0.6]]
        client = self._make_client()
        result = client.generar_embeddings_batch(["test"])
        assert result == [[0.5, 0.6]]
        mock_embed.assert_called_with(["test"], model="nomic-embed-text")
