"""Tests for core: ejecutor_seguro, internet, change_guardian, error_sandbox, alert_manager."""

import logging
from unittest.mock import MagicMock, patch


logging.disable(logging.CRITICAL)


class TestEjecutorSeguro:
    def test_imports(self):
        from core.ejecutor_seguro import ejecutar

        assert callable(ejecutar)

    @patch("core.ejecutor_seguro.subprocess.run")
    def test_returns_dict_on_success(self, mock_run: MagicMock):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        from core.ejecutor_seguro import ejecutar

        result = ejecutar("echo hola")
        assert isinstance(result, dict)
        assert "ok" in result


class TestInternet:
    def test_imports(self):
        from core.internet import get

        assert callable(get)

    @patch("core.internet.requests.get")
    def test_returns_dict(self, mock_get: MagicMock):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_get.return_value = mock_response
        from core.internet import get

        result = get("http://example.com")
        assert isinstance(result, dict)


class TestChangeGuardian:
    def test_imports(self):
        from core.change_guardian import ChangeGuardian

        assert ChangeGuardian is not None


class TestErrorSandbox:
    def test_imports(self):
        from core.error_sandbox import ErrorSandbox

        assert ErrorSandbox is not None


class TestAlertManager:
    def test_imports(self):
        from core.alert_manager import AlertManager, ErrorPriority, ErrorStatus

        assert AlertManager is not None
        assert ErrorPriority is not None
        assert ErrorStatus is not None

    def test_instantiates(self):
        from core.alert_manager import AlertManager

        am = AlertManager()
        assert am is not None
