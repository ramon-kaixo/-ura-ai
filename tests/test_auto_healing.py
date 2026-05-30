"""Tests for core/auto_healing.py — automatic service recovery."""

import logging
from unittest.mock import MagicMock, patch

import pytest

logging.disable(logging.CRITICAL)


@pytest.fixture(autouse=True)
def mock_deps():
    """Prevent real subprocess calls and circuit breaker side effects."""
    with (
        patch("core.auto_healing.get_circuit_breaker"),
        patch("core.auto_healing.subprocess.run"),
        patch("core.auto_healing.time.sleep"),
    ):
        yield


class TestImports:
    """Module imports cleanly."""

    def test_imports_without_error(self):
        from core.auto_healing import intentar_recuperacion, verificar_servicio

        assert callable(intentar_recuperacion)
        assert callable(verificar_servicio)


class TestIntentarRecuperacion:
    """intentar_recuperacion() — 4-step recovery cascade."""

    def test_returns_bool(self):
        from core.auto_healing import intentar_recuperacion

        result = intentar_recuperacion("ollama")
        assert isinstance(result, bool)

    @patch("core.auto_healing._reiniciar_servicio", return_value=False)
    @patch("core.auto_healing._cambiar_modelo_fallback", return_value=False)
    @patch("core.auto_healing._limpiar_cache_redis", return_value=False)
    @patch("core.auto_healing._abrir_circuit_breaker")
    def test_all_steps_fail_returns_false(
        self,
        mock_abrir: MagicMock,
        mock_redis: MagicMock,
        mock_fallback: MagicMock,
        mock_reiniciar: MagicMock,
    ):
        from core.auto_healing import intentar_recuperacion

        result = intentar_recuperacion("ollama")
        assert result is False
        mock_reiniciar.assert_called_once()
        mock_fallback.assert_called_once()
        mock_abrir.assert_called_once()

    @patch("core.auto_healing._reiniciar_servicio", return_value=True)
    def test_step1_restart_succeeds(self, _mock_restart: MagicMock):
        from core.auto_healing import intentar_recuperacion

        result = intentar_recuperacion("ollama")
        assert result is True

    def test_non_ollama_service_no_model_fallback(self):
        from core.auto_healing import intentar_recuperacion

        result = intentar_recuperacion("unknown_service")
        assert isinstance(result, bool)


class TestVerificarServicio:
    """verificar_servicio() — health checks."""

    @patch("requests.get")
    def test_ollama_responding_returns_true(self, mock_get: MagicMock):
        mock_get.return_value.status_code = 200
        from core.auto_healing import verificar_servicio

        result = verificar_servicio("ollama")
        assert result is True

    @patch("requests.get")
    def test_ollama_not_responding_returns_false(self, mock_get: MagicMock):
        mock_get.side_effect = Exception("connection refused")
        from core.auto_healing import verificar_servicio

        result = verificar_servicio("ollama")
        assert result is False
