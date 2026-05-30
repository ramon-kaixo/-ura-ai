"""Tests for core/cloud_backup.py — iCloud backup via brctl and rsync."""

import logging
from unittest.mock import MagicMock, patch


logging.disable(logging.CRITICAL)


class TestImports:
    """Verify module imports cleanly."""

    def test_imports_without_error(self):
        from core.cloud_backup import hacer_backup

        assert callable(hacer_backup)


class TestNonMacOS:
    """hacer_backup() on non-macOS systems."""

    def test_non_darwin_returns_ok_false(self):
        with patch("core.cloud_backup.sys.platform", "linux"):
            from core.cloud_backup import hacer_backup

            result = hacer_backup()
            assert result["ok"] is False
            assert result["archivos"] == 0
            assert result["duracion_segundos"] == 0.0
            assert "macOS" in result["error"]


class TestMockedBackup:
    """hacer_backup() with mocked ejecutor_seguro."""

    @patch("core.cloud_backup.Path.mkdir")
    @patch("core.cloud_backup.Path.rglob")
    @patch("core.cloud_backup.sys.platform", "darwin")
    def test_successful_backup_returns_expected_keys(
        self, mock_rglob: MagicMock, _mock_mkdir: MagicMock
    ):
        mock_rglob.return_value = [MagicMock()] * 42

        with patch("core.cloud_backup.ejecutar") as mock_ejecutar:
            mock_ejecutar.side_effect = [
                {"ok": True, "stdout": "brctl ok", "stderr": ""},
                {"ok": True, "stdout": "rsync done", "stderr": ""},
            ]
            from core.cloud_backup import hacer_backup

            result = hacer_backup()

        assert result["ok"] is True
        assert result["archivos"] == 42
        assert result["duracion_segundos"] > 0
        assert result["error"] is None

    @patch("core.cloud_backup.Path.mkdir")
    @patch("core.cloud_backup.sys.platform", "darwin")
    def test_brctl_unavailable_returns_ok_false(self, _mock_mkdir: MagicMock):
        with patch("core.cloud_backup.ejecutar") as mock_ejecutar:
            mock_ejecutar.return_value = {
                "ok": False,
                "stdout": "",
                "stderr": "brctl: command not found",
            }
            from core.cloud_backup import hacer_backup

            result = hacer_backup()

        assert result["ok"] is False
        assert "iCloud no disponible" in result["error"]

    @patch("core.cloud_backup.Path.mkdir")
    @patch("core.cloud_backup.sys.platform", "darwin")
    def test_brctl_exception_returns_ok_false(self, _mock_mkdir: MagicMock):
        with patch("core.cloud_backup.ejecutar") as mock_ejecutar:
            mock_ejecutar.side_effect = OSError("disk full")
            from core.cloud_backup import hacer_backup

            result = hacer_backup()

        assert result["ok"] is False
        assert "Error verificando iCloud" in result["error"]

    @patch("core.cloud_backup.Path.mkdir")
    @patch("core.cloud_backup.sys.platform", "darwin")
    def test_rsync_failure_returns_ok_false(self, _mock_mkdir: MagicMock):
        with patch("core.cloud_backup.ejecutar") as mock_ejecutar:
            mock_ejecutar.side_effect = [
                {"ok": True, "stdout": "brctl ok", "stderr": ""},
                {"ok": False, "stdout": "", "stderr": "permission denied"},
            ]
            from core.cloud_backup import hacer_backup

            result = hacer_backup()

        assert result["ok"] is False
        assert "rsync falló" in result["error"]

    @patch("core.cloud_backup.Path.mkdir")
    @patch("core.cloud_backup.sys.platform", "darwin")
    def test_rsync_exception_returns_ok_false(self, _mock_mkdir: MagicMock):
        with patch("core.cloud_backup.ejecutar") as mock_ejecutar:
            mock_ejecutar.side_effect = [
                {"ok": True, "stdout": "brctl ok", "stderr": ""},
                OSError("no space left"),
            ]
            from core.cloud_backup import hacer_backup

            result = hacer_backup()

        assert result["ok"] is False
        assert "Error ejecutando rsync" in result["error"]
