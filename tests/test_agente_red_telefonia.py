"""Tests for agents/agente_red_telefonia.py — WiFi, router and network monitoring."""

import logging
from unittest.mock import patch

import pytest

logging.disable(logging.CRITICAL)


@pytest.fixture(autouse=True)
def _mock_ejecutar():
    """Prevent real shell calls; ejecutar() returns predictable output."""
    with patch("agents.agente_red_telefonia.ejecutar") as mock_ejecutar:
        mock_ejecutar.return_value = {
            "ok": True,
            "stdout": "Current Wi-Fi Network: MiWiFi\nrtt min/avg/max/mdev = 1/12.5/30/5",
            "stderr": "",
            "codigo": 0,
        }
        yield mock_ejecutar


@pytest.fixture(autouse=True)
def _mock_requests():
    """Prevent real HTTP calls; requests.get raises ConnectionError by default."""
    with patch("agents.agente_red_telefonia.requests") as mock_req:
        mock_req.get.side_effect = Exception("network unreachable")
        mock_req.post.side_effect = Exception("network unreachable")
        yield mock_req


class TestInstantiation:
    def test_imports_without_error(self):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        assert AgenteRedTelefonia is not None

    def test_instantiates_with_expected_attributes(self):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        agente = AgenteRedTelefonia()
        assert agente.estado_anterior == "ok"
        assert agente.ROUTER_IP == "192.168.1.1"
        assert agente.LATENCIA_ALERTA_MS == 100


class TestEstadoWifi:
    def test_returns_expected_keys(self):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        result = AgenteRedTelefonia().estado_wifi()
        for key in ("conectado", "ssid", "latencia_ms", "estado"):
            assert key in result

    def test_conectado_is_bool_and_latencia_is_float(self):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        result = AgenteRedTelefonia().estado_wifi()
        assert isinstance(result["conectado"], bool)
        assert isinstance(result["latencia_ms"], float)

    def test_estado_ok_when_latencia_baja(self):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        result = AgenteRedTelefonia().estado_wifi()
        # ping mock devuelve 12.5 → bajo el umbral
        assert result["estado"] == "ok"


class TestEstadoRouter:
    def test_unreachable_router_returns_ok_false(self):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        result = AgenteRedTelefonia().estado_router()
        assert result["ok"] is False
        assert result["ip"] == "192.168.1.1"
        assert "error" in result


class TestDispositivosConectados:
    def test_returns_list(self, _mock_ejecutar):
        _mock_ejecutar.return_value = {
            "ok": True,
            "stdout": "host1 (192.168.1.5) at aa:bb:cc\nhost2 (192.168.1.6) at dd:ee:ff",
            "stderr": "",
            "codigo": 0,
        }
        from agents.agente_red_telefonia import AgenteRedTelefonia

        result = AgenteRedTelefonia().dispositivos_conectados()
        assert isinstance(result, list)
        assert len(result) == 2


class TestMonitorear:
    def test_returns_dict_with_expected_keys(self):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        result = AgenteRedTelefonia().monitorear()
        for key in ("wifi", "router", "estado"):
            assert key in result
        assert result["estado"] in ("ok", "sin_wifi", "lento", "router_caido")

    def test_wifi_subdict_has_keys(self):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        result = AgenteRedTelefonia().monitorear()
        for key in ("conectado", "ssid", "latencia_ms", "estado"):
            assert key in result["wifi"]

    def test_router_caido_cuando_no_responde(self):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        # WiFi conectado + ping ok + router unreachable → "router_caido"
        result = AgenteRedTelefonia().monitorear()
        assert result["estado"] == "router_caido"


class TestAutoAccion:
    def test_no_exception_with_known_problems(self):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        agente = AgenteRedTelefonia()
        for problema in ("sin_wifi", "router_caido", "lento", "desconocido"):
            try:
                agente._auto_accion(problema)
            except Exception as e:
                pytest.fail(f"_auto_accion({problema!r}) raised: {e}")

    def test_sin_wifi_intenta_reconectar(self, _mock_ejecutar):
        from agents.agente_red_telefonia import AgenteRedTelefonia

        with patch("agents.agente_red_telefonia.time.sleep"):
            AgenteRedTelefonia()._auto_accion("sin_wifi")
        # Debe haber llamado a ejecutar al menos 2 veces (off + on)
        calls = [c for c in _mock_ejecutar.call_args_list if "setairportpower" in str(c)]
        assert len(calls) >= 2
