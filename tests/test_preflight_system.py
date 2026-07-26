"""Tests para preflight_system.py (system manifest + pre-flight check)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from scripts.pro.tuneladora.preflight_system import (
    _audit_ports,
    _audit_services,
    _ss_ports,
    check_manifest_service,
    check_port,
    check_screen_exists,
    check_systemd_service,
    load_manifest,
    preflight,
)

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "deploy" / "system_manifest.json"


# ── Fixtures ──


@pytest.fixture
def sample_manifest() -> dict:
    return {
        "version": "2026-07-26",
        "hostname": "gx10-64c3",
        "services": {
            "system": {
                "ura-mochila": {"port": 4098, "status": "active", "description": "API"},
                "model-router": {"port": 11435, "status": "active", "description": "Router"},
            },
            "user": {},
        },
        "ports": {
            "4098": "ura-mochila",
            "11435": "model-router",
        },
    }


# ── Tests: check_systemd_service ──


class TestCheckSystemdService:
    def test_active_system(self):
        with mock.patch("subprocess.run") as m:
            m.side_effect = [
                mock.Mock(stdout="loaded\n"),    # show system
                mock.Mock(stdout="active\n"),    # is-active system
                mock.Mock(stdout="not-found\n"), # show user
            ]
            result = check_systemd_service("ura-mochila")
            assert result["exists"] is True
            assert result["active"] is True
            assert "system" in result["scopes"]

    def test_inactive_service(self):
        with mock.patch("subprocess.run") as m:
            m.side_effect = [
                mock.Mock(stdout="loaded\n"),    # show system
                mock.Mock(stdout="inactive\n"),  # is-active system
                mock.Mock(stdout="not-found\n"), # show user
            ]
            result = check_systemd_service("old-service")
            assert result["exists"] is True
            assert result["active"] is False

    def test_not_found(self):
        with mock.patch("subprocess.run") as m:
            m.side_effect = [
                mock.Mock(stdout="not-found\n"), # show system
                mock.Mock(stdout="not-found\n"), # show user
            ]
            result = check_systemd_service("nonexistent")
            assert result["exists"] is False
            assert result["active"] is False
            assert result["scopes"] == []

    def test_user_scope(self):
        def side_effect(*args, **kwargs):
            cmd = kwargs.get("args") or args[0]
            is_show = "--property=LoadState" in cmd
            if "--user" in cmd and is_show:
                return mock.Mock(stdout="loaded\n")
            if "--user" in cmd:
                return mock.Mock(stdout="active\n")
            if is_show:
                return mock.Mock(stdout="not-found\n")
            return mock.Mock(stdout="inactive\n")

        with mock.patch("subprocess.run", side_effect=side_effect):
            result = check_systemd_service("user-service")
            assert result["exists"] is True
            assert "user" in result["scopes"]
            assert result["active"] is True


# ── Tests: check_port ──


_SS_OUTPUT = """LISTEN 0 4096 127.0.0.1:4098 0.0.0.0:*    users:((\"python3\",pid=1234,fd=13))
LISTEN 0 4096 0.0.0.0:11435 0.0.0.0:*    users:((\"python3\",pid=5678,fd=3))
LISTEN 0 4096 0.0.0.0:3080 0.0.0.0:*    users:((\"docker-proxy\",pid=9012,fd=8))
LISTEN 0 50 0.0.0.0:139 0.0.0.0:*
LISTEN 0 4096 [::]:22 [::]:*
"""


class TestCheckPort:
    def test_port_in_use(self):
        with mock.patch("subprocess.run") as m:
            m.return_value = mock.Mock(stdout=_SS_OUTPUT)
            result = check_port(4098)
            assert result["in_use"] is True
            assert "python3" in (result["process"] or "")

    def test_port_free(self):
        with mock.patch("subprocess.run") as m:
            m.return_value = mock.Mock(stdout=_SS_OUTPUT)
            result = check_port(9999)
            assert result["in_use"] is False
            assert result["process"] is None

    def test_port_used_by_docker(self):
        with mock.patch("subprocess.run") as m:
            m.return_value = mock.Mock(stdout=_SS_OUTPUT)
            result = check_port(3080)
            assert result["in_use"] is True
            assert "docker-proxy" in (result["process"] or "")


# ── Tests: _ss_ports ──


class TestSsPorts:
    def test_extracts_ports(self):
        result = _ss_ports(_SS_OUTPUT)
        ports = {p for p, _ in result}
        assert "4098" in ports
        assert "11435" in ports
        assert "3080" in ports
        assert "139" in ports
        assert "22" in ports

    def test_skips_non_listen(self):
        result = _ss_ports("ESTAB 0 0 127.0.0.1:4098 10.0.0.1:80")
        assert len(result) == 0


# ── Tests: check_screen_exists ──


class TestCheckScreen:
    def test_screen_exists(self):
        with mock.patch("subprocess.run") as m:
            m.return_value = mock.Mock(stdout="There is a screen on 1234.pts-0.gx10\tura-main\n")
            assert check_screen_exists("ura-main") is True

    def test_screen_not_found(self):
        with mock.patch("subprocess.run") as m:
            m.return_value = mock.Mock(stdout="No Sockets found.\n")
            assert check_screen_exists("ura-main") is False


# ── Tests: load_manifest / check_manifest_service ──


class TestManifest:
    def test_real_manifest_exists(self):
        assert MANIFEST_PATH.exists(), f"Manifest no encontrado: {MANIFEST_PATH}"

    def test_real_manifest_is_valid_json(self):
        data = json.loads(MANIFEST_PATH.read_text())
        assert "version" in data
        assert "services" in data
        assert "ports" in data

    def test_real_manifest_has_required_sections(self):
        data = json.loads(MANIFEST_PATH.read_text())
        assert "ura-mochila" in data.get("services", {}).get("system", {})
        assert "model-router" in data.get("services", {}).get("system", {})
        assert len(data.get("ports", {})) > 10

    def test_load_manifest_file_not_found(self, tmp_path):
        with mock.patch("scripts.pro.tuneladora.preflight_system.MANIFEST", tmp_path / "nonexistent.json"):
            assert load_manifest() == {}

    def test_check_manifest_service_found(self, sample_manifest):
        result = check_manifest_service(sample_manifest, "ura-mochila")
        assert result is not None
        assert result["port"] == 4098

    def test_check_manifest_service_not_found(self, sample_manifest):
        assert check_manifest_service(sample_manifest, "nonexistent") is None

    def test_check_manifest_user_service(self, sample_manifest):
        assert check_manifest_service(sample_manifest, "nonexistent-user") is None


# ── Tests: preflight ──


class TestPreflight:
    def test_ok_for_new_service(self, sample_manifest):
        with (
            mock.patch("scripts.pro.tuneladora.preflight_system.load_manifest", return_value=sample_manifest),
            mock.patch("scripts.pro.tuneladora.preflight_system.check_systemd_service") as mock_svc,
            mock.patch("scripts.pro.tuneladora.preflight_system.check_port") as mock_port,
            mock.patch("scripts.pro.tuneladora.preflight_system.check_screen_exists", return_value=False),
        ):
            mock_svc.return_value = {"exists": False, "active": False, "scopes": []}
            mock_port.return_value = {"in_use": False, "process": None}
            assert preflight("new-service", 9999) is True

    def test_blocks_duplicate_service(self, sample_manifest):
        with (
            mock.patch("scripts.pro.tuneladora.preflight_system.load_manifest", return_value=sample_manifest),
            mock.patch("scripts.pro.tuneladora.preflight_system.check_systemd_service") as mock_svc,
            mock.patch("scripts.pro.tuneladora.preflight_system.check_port") as mock_port,
        ):
            mock_svc.return_value = {"exists": True, "active": True, "scopes": ["system"]}
            mock_port.return_value = {"in_use": True, "process": "old process"}
            assert preflight("model-router", 11435) is False

    def test_blocks_duplicate_port(self, sample_manifest):
        with (
            mock.patch("scripts.pro.tuneladora.preflight_system.load_manifest", return_value=sample_manifest),
            mock.patch("scripts.pro.tuneladora.preflight_system.check_systemd_service") as mock_svc,
            mock.patch("scripts.pro.tuneladora.preflight_system.check_port") as mock_port,
        ):
            mock_svc.return_value = {"exists": False, "active": False, "scopes": []}
            mock_port.return_value = {"in_use": True, "process": "other process"}
            result = preflight("new-service", 4098)
            assert result is False


# ── Tests: _audit_services ──


class TestAuditServices:
    def test_active_service_no_issues(self, sample_manifest):
        issues: list[str] = []
        with mock.patch("scripts.pro.tuneladora.preflight_system.check_systemd_service") as m:
            m.return_value = {"exists": True, "active": True, "scopes": ["system"]}
            _audit_services(sample_manifest, issues)
            assert issues == []

    def test_missing_service_reported(self, sample_manifest):
        issues: list[str] = []
        with mock.patch("scripts.pro.tuneladora.preflight_system.check_systemd_service") as m:
            m.return_value = {"exists": False, "active": False, "scopes": []}
            _audit_services(sample_manifest, issues)
            assert any("ura-mochila" in i for i in issues)
            assert any("NO en systemd" in i for i in issues)

    def test_inactive_service_reported(self, sample_manifest):
        issues: list[str] = []
        with mock.patch("scripts.pro.tuneladora.preflight_system.check_systemd_service") as m:
            m.return_value = {"exists": True, "active": False, "scopes": ["system(inactive)"]}
            _audit_services(sample_manifest, issues)
            assert any("active" in i and "NO activo" in i for i in issues)


# ── Tests: _audit_ports ──


class TestAuditPorts:
    def test_all_ports_registered(self):
        manifest = {"ports": {"4098": "ura-mochila", "22": "ssh"}}
        issues: list[str] = []
        with mock.patch("scripts.pro.tuneladora.preflight_system._ss_ports") as m:
            m.return_value = [("4098", "line.."), ("22", "line..")]
            _audit_ports(manifest, issues)
            assert issues == []

    def test_unregistered_port_reported(self):
        manifest = {"ports": {"4098": "ura-mochila"}}
        issues: list[str] = []
        with mock.patch("scripts.pro.tuneladora.preflight_system._ss_ports") as m:
            m.return_value = [("4098", "line.."), ("9999", "line..")]
            _audit_ports(manifest, issues)
            assert any("9999" in i for i in issues)

    def test_ephemeral_port_filtered(self):
        manifest = {"ports": {"4098": "ura-mochila"}}
        issues: list[str] = []
        with mock.patch("scripts.pro.tuneladora.preflight_system._ss_ports") as m:
            m.return_value = [("4098", "line.."), ("54321", "line.. tailscale")]
            _audit_ports(manifest, issues)
            assert issues == []

    def test_orphaned_port_reported(self):
        manifest = {"ports": {"4098": "ura-mochila", "9999": "old-service"}}
        issues: list[str] = []
        with mock.patch("scripts.pro.tuneladora.preflight_system._ss_ports") as m:
            m.return_value = [("4098", "line..")]
            _audit_ports(manifest, issues)
            assert any("no escuchando" in i for i in issues)


# ── Integration test: real manifest validity ──


class TestRealManifestIntegration:
    """Tests que validan el manifiesto real contra el sistema."""

    def test_manifest_services_have_required_fields(self):
        data = json.loads(MANIFEST_PATH.read_text())
        for name, info in data.get("services", {}).get("system", {}).items():
            assert "status" in info, f"{name}: falta status"
            assert "description" in info, f"{name}: falta description"
            assert isinstance(info.get("status"), str), f"{name}: status debe ser string"

    def test_manifest_ports_are_strings(self):
        data = json.loads(MANIFEST_PATH.read_text())
        for port, owner in data.get("ports", {}).items():
            assert isinstance(port, str), f"Puerto {port} debe ser string"
            assert isinstance(owner, str), f"Owner de {port} debe ser string"
            assert port.isdigit(), f"Puerto {port} debe ser numérico"

    def test_manifest_hostname_matches(self):
        import socket

        data = json.loads(MANIFEST_PATH.read_text())
        hostname = socket.gethostname()
        assert data.get("hostname") == hostname, (
            f"Manifiesto dice {data.get('hostname')}, host real es {hostname}"
        )
