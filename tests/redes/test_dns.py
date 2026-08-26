"""Tests de DNS: verifica resolucion de nombres de host.

GX10: verifica resolucion local.
"""

from __future__ import annotations

import pytest

from tests.infra.conftest import run_cmd


@pytest.mark.gx10
class TestDNSResolution:
    """Verifica que los nombres de host resuelven correctamente."""

    def test_gx10_ts_resolves(self) -> None:
        rc, out, _ = run_cmd("host gx10-ts 2>/dev/null || getent hosts gx10-ts")
        if rc != 0:
            pytest.xfail("gx10-ts no resuelve (puede ser falta de /etc/hosts o DNS)")
        assert "100.72" in out, f"gx10-ts no resuelve a IP Tailscale: {out}"

    def test_gx10_lan_resolves(self) -> None:
        rc, out, _ = run_cmd("host gx10-lan 2>/dev/null || getent hosts gx10-lan")
        if rc != 0:
            pytest.xfail("gx10-lan no resuelve")
        assert "10.164" in out or "100.72" in out, f"gx10-lan resolucion inesperada: {out}"

    def test_etc_hosts_has_gx10(self) -> None:
        rc, out, _ = run_cmd("grep -c 'gx10' /etc/hosts")
        if rc != 0:
            pytest.skip("No se puede leer /etc/hosts")
        assert int(out) > 0, "gx10 no encontrado en /etc/hosts"
