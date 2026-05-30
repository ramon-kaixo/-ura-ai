"""Tests for core/network_audit.py — network port audit and API health."""

import logging
from unittest.mock import MagicMock, patch


logging.disable(logging.CRITICAL)


class TestInstantiation:
    """NetworkAuditSystem instancia sin errores."""

    def test_imports_without_error(self):
        from core.network_audit import NetworkAuditSystem

        assert NetworkAuditSystem is not None

    def test_instantiates_without_error(self):
        from core.network_audit import NetworkAuditSystem

        nas = NetworkAuditSystem()
        assert nas is not None
        assert hasattr(nas, "inventory")
        assert hasattr(nas, "FIXED_ASSIGNMENTS")
        assert hasattr(nas, "ALLOWED_PORTS")
        assert hasattr(nas, "RESERVE_PORTS")

    def test_localhost_mode(self):
        from core.network_audit import NetworkAuditSystem

        nas = NetworkAuditSystem(use_localhost=True)
        assert nas.use_localhost is True


class TestFixedAssignments:
    """Tabla de asignacion fija."""

    def test_ollama_port_assigned(self):
        from core.network_audit import NetworkAuditSystem

        nas = NetworkAuditSystem()
        assert "ollama" in nas.FIXED_ASSIGNMENTS
        assert nas.FIXED_ASSIGNMENTS["ollama"]["port"] == 11434

    def test_windsurf_port_assigned(self):
        from core.network_audit import NetworkAuditSystem

        nas = NetworkAuditSystem()
        assert nas.FIXED_ASSIGNMENTS["windsurf"]["port"] == 3000

    def test_five_reserve_ports(self):
        from core.network_audit import NetworkAuditSystem

        nas = NetworkAuditSystem()
        assert len(nas.RESERVE_PORTS) == 5


class TestAllowedPorts:
    """Lista maestra de puertos permitidos."""

    def test_ollama_11434_allowed(self):
        from core.network_audit import NetworkAuditSystem

        nas = NetworkAuditSystem()
        assert 11434 in nas.ALLOWED_PORTS

    def test_redis_6379_allowed(self):
        from core.network_audit import NetworkAuditSystem

        nas = NetworkAuditSystem()
        assert 6379 in nas.ALLOWED_PORTS

    def test_unknown_port_not_allowed(self):
        from core.network_audit import NetworkAuditSystem

        nas = NetworkAuditSystem()
        assert 99999 not in nas.ALLOWED_PORTS


class TestRunFullAudit:
    """run_full_audit() devuelve dict con claves esperadas."""

    @patch("core.network_audit.subprocess.run")
    def test_returns_dict_with_expected_keys(self, _mock_subprocess: MagicMock):
        from core.network_audit import NetworkAuditSystem

        nas = NetworkAuditSystem(use_localhost=True)
        result = nas.run_full_audit()
        assert isinstance(result, dict)
        for key in (
            "timestamp",
            "total_ports",
            "docker_ports",
            "native_ports",
            "api_health",
            "fixed_assignments",
            "reserve_ports",
            "use_localhost",
        ):
            assert key in result, f"Missing key: {key}"

    @patch("core.network_audit.subprocess.run")
    def test_total_ports_is_int(self, _mock_subprocess: MagicMock):
        from core.network_audit import NetworkAuditSystem

        nas = NetworkAuditSystem(use_localhost=True)
        result = nas.run_full_audit()
        assert isinstance(result["total_ports"], int)
