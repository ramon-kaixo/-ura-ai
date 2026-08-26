"""Tests de conectividad: verifica que las maquinas se alcanzan por Tailscale.

GX10: ping a localhost Tailscale y Mac.
Mac: ping a GX10.
"""

from __future__ import annotations

import pytest

from tests.infra.conftest import run_cmd
from tests.redes import GX10_TS_IP, MAC_TS_IP


@pytest.mark.gx10
class TestGX10Connectivity:
    """Tests de conectividad desde GX10."""

    def test_gx10_self_ping(self) -> None:
        rc, out, _ = run_cmd(f"ping -c 2 -W 2 {GX10_TS_IP}")
        assert rc == 0, f"GX10 no responde a ping en su propia IP Tailscale: {out}"

    def test_gx10_to_mac(self) -> None:
        rc, out, _ = run_cmd(f"ping -c 2 -W 3 {MAC_TS_IP}")
        if rc != 0:
            pytest.xfail("Mac apagado o inalcanzable (no es fallo critico)")
        assert rc == 0, f"No se puede alcanzar Mac: {out}"


@pytest.mark.mac
class TestMacConnectivity:
    """Tests de conectividad desde Mac."""

    def test_mac_to_gx10(self) -> None:
        rc, out, _ = run_cmd(f"ping -c 2 -W 3 {GX10_TS_IP}")
        assert rc == 0, f"No se puede alcanzar GX10: {out}"

    def test_mac_to_gx10_hostname(self) -> None:
        rc, _, _ = run_cmd("ping -c 2 -W 3 gx10-ts")
        if rc != 0:
            pytest.xfail("gx10-ts no resuelve (puede ser falta de /etc/hosts o DNS)")
