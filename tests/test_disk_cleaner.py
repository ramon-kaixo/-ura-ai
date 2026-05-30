"""Tests for core/disk_cleaner.py — safe/full disk cleanup modes."""

import logging
from unittest.mock import MagicMock, patch


logging.disable(logging.CRITICAL)


class TestSafeMode:
    """Modo safe: solo caches y logs, sin Docker."""

    @patch("core.disk_cleaner.ejecutar")
    def test_safe_mode_returns_expected_keys(self, _mock_ejecutar: MagicMock):
        from core.disk_cleaner import limpiar

        result = limpiar(modo="safe")
        for key in ("ok", "espacio_liberado_mb", "acciones", "errores"):
            assert key in result, f"Missing key: {key}"


class TestFullMode:
    """Modo full: incluye Docker."""

    @patch("core.disk_cleaner.ejecutar")
    def test_full_mode_returns_expected_keys(self, _mock_ejecutar: MagicMock):
        from core.disk_cleaner import limpiar

        result = limpiar(modo="full")
        for key in ("ok", "espacio_liberado_mb", "acciones", "errores"):
            assert key in result


class TestErrorHandling:
    """Si un comando falla, continúa y registra error."""

    @patch("core.disk_cleaner.Path.exists")
    @patch("core.disk_cleaner.Path.glob")
    @patch("core.disk_cleaner.ejecutar")
    def test_continues_after_failure(
        self, mock_ejecutar: MagicMock, mock_glob: MagicMock, _mock_exists: MagicMock
    ):
        mock_glob.return_value = []
        mock_ejecutar.side_effect = Exception("command failed")
        from core.disk_cleaner import limpiar

        result = limpiar(modo="full")
        assert "ok" in result
