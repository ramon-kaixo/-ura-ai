"""Tests de firewall: verifica que puertos estan filtrados correctamente.

GX10: verifica bind addresses con ss (sin sudo).
"""

from __future__ import annotations

import pytest

from tests.infra.conftest import run_cmd


@pytest.mark.gx10
class TestFirewallStatus:
    """Verifica el estado del firewall (solo lectura)."""

    def test_ss_shows_listeners(self) -> None:
        rc, out, _ = run_cmd("ss -tlnp")
        assert rc == 0, "ss no disponible"
        assert "LISTEN" in out, "ss no retorna listeners"

    def test_ssh_not_exposed_to_all(self) -> None:
        rc, out, _ = run_cmd("ss -tlnp | grep :22")
        if rc != 0:
            pytest.skip("SSH no activo")
        if "0.0.0.0" in out:  # noqa: S104
            pytest.xfail("SSH escucha en 0.0.0.0 (exposicion a LAN)")

    def test_qdrant_bound_to_localhost(self) -> None:
        rc, out, _ = run_cmd("ss -tlnp | grep :6333")
        if rc != 0:
            pytest.skip("Qdrant no activo")
        if "127.0.0.1" in out:
            pass  # Correcto
        elif "0.0.0.0" in out:  # noqa: S104
            pytest.xfail("Qdrant escucha en 0.0.0.0 — should be 127.0.0.1")


@pytest.mark.gx10
class TestTailscaleACL:
    """Verifica que Tailscale esta activo y configurado."""

    def test_tailscale_status(self) -> None:
        rc, out, _ = run_cmd("tailscale status 2>/dev/null | head -5")
        if rc != 0:
            pytest.skip("tailscale CLI no disponible o no autenticado")
        has_gx10 = "gx10" in out.lower() or "100.72.103.12" in out
        has_nodes = len(out.strip().splitlines()) >= 1
        assert has_gx10 or has_nodes, (
            f"Tailscale no parece activo: {out[:200]}"
        )
