"""Tests for agents/agente_conectividad.py — multi-IP connectivity."""

import logging
from unittest.mock import MagicMock, patch

import pytest

logging.disable(logging.CRITICAL)


@pytest.fixture(autouse=True)
def mock_deps():
    """Prevent real network calls and file I/O."""
    mock_ejecutar = MagicMock()
    mock_ejecutar.return_value = {"ok": True, "stdout": "ok", "stderr": ""}
    with (
        patch("agents.agente_conectividad.ejecutar", mock_ejecutar),
        patch("agents.agente_conectividad.Path.write_text"),
        patch("agents.agente_conectividad.Path.mkdir"),
    ):
        yield


class TestInstantiation:
    """AgenteConectividad instancia sin errores."""

    def test_imports_without_error(self):
        from agents.agente_conectividad import AgenteConectividad

        assert AgenteConectividad is not None

    def test_instantiates_without_error(self):
        from agents.agente_conectividad import AgenteConectividad

        agente = AgenteConectividad()
        assert agente is not None
        assert hasattr(agente, "proveedor_activo")
        assert hasattr(agente, "ip_publica_actual")
        assert hasattr(agente, "historial")

    def test_proveedores_defined(self):
        from agents.agente_conectividad import AgenteConectividad

        agente = AgenteConectividad()
        assert len(agente.PROVEEDORES) == 3
        prioridades = [p["prioridad"] for p in agente.PROVEEDORES]
        assert prioridades == sorted(prioridades)


class TestDetectarMejorProveedor:
    """detectar_mejor_proveedor() — provider detection and switching."""

    @patch("agents.agente_conectividad.requests.get")
    def test_returns_ok_and_proveedor_on_success(self, mock_get: MagicMock):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ip": "1.2.3.4"}
        mock_get.return_value = mock_response

        from agents.agente_conectividad import AgenteConectividad

        agente = AgenteConectividad()
        result = agente.detectar_mejor_proveedor()
        assert result["ok"] is True
        assert "proveedor" in result
        assert "ip" in result

    def test_all_providers_down_returns_ok_false(self):
        from agents.agente_conectividad import AgenteConectividad

        agente = AgenteConectividad()
        agente._verificar_proveedor = MagicMock(return_value=False)
        result = agente.detectar_mejor_proveedor()
        assert result["ok"] is False
        assert "error" in result


class TestIpPublica:
    """ip_publica() — public IP info."""

    @patch("agents.agente_conectividad.requests.get")
    def test_returns_expected_keys(self, mock_get: MagicMock):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ip": "5.6.7.8"}
        mock_get.return_value = mock_response

        from agents.agente_conectividad import AgenteConectividad

        agente = AgenteConectividad()
        result = agente.ip_publica()
        for key in ("ip", "proveedor", "fija"):
            assert key in result, f"Missing key: {key}"

    @patch("agents.agente_conectividad.requests.get")
    def test_ip_is_string(self, mock_get: MagicMock):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ip": "9.10.11.12"}
        mock_get.return_value = mock_response

        from agents.agente_conectividad import AgenteConectividad

        agente = AgenteConectividad()
        result = agente.ip_publica()
        assert isinstance(result["ip"], str)

    @patch("agents.agente_conectividad.requests.get")
    def test_fija_is_bool(self, mock_get: MagicMock):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ip": "0.0.0.0"}
        mock_get.return_value = mock_response

        from agents.agente_conectividad import AgenteConectividad

        agente = AgenteConectividad()
        result = agente.ip_publica()
        assert isinstance(result["fija"], bool)


class TestFlujoInfo:
    """flujo_info() — complete network flow info."""

    @patch("agents.agente_conectividad.requests.get")
    def test_returns_all_expected_keys(self, mock_get: MagicMock):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ip": "10.0.0.1"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from agents.agente_conectividad import AgenteConectividad

        agente = AgenteConectividad()
        result = agente.flujo_info()
        expected = (
            "ip_publica",
            "ip_fija",
            "proveedor_activo",
            "tunnel_cloudflare",
            "tunnels",
            "historial_cambios",
            "ultimo_cambio",
        )
        for key in expected:
            assert key in result, f"Missing key: {key}"


class TestGuardarEstado:
    """_guardar_estado() — persistent state save."""

    def test_does_not_raise_exception(self):
        from agents.agente_conectividad import AgenteConectividad

        agente = AgenteConectividad()
        try:
            agente._guardar_estado()
        except Exception as e:
            pytest.fail(f"_guardar_estado raised: {e}")
