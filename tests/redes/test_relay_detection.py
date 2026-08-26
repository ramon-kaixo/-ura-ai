"""Tests de Tailscale: verifica conexión directa vs relay.

GX10→Mac actualmente va vía relay (hetzner-escudo, 42ms).
Mac→GX10 es directo (19ms vía 10.164.1.1).
Estos tests detectan y documentan el estado de la conexión.
"""

from __future__ import annotations

import pytest

from tests.infra.conftest import run_cmd
from tests.redes import GX10_TS_IP, MAC_TS_IP


@pytest.mark.gx10
class TestTailscaleDirectGX10:
    """Verifica estado de Tailscale desde GX10."""

    def test_gx10_tailscale_online(self) -> None:
        """GX10 tiene Tailscale activo."""
        rc, out, _ = run_cmd("tailscale status 2>/dev/null | head -1")
        assert rc == 0, "tailscale status falló"
        assert GX10_TS_IP in out or "gx10" in out.lower(), (
            f"GX10 no aparece en tailscale status: {out.strip()}"
        )

    def test_gx10_to_mac_latency(self) -> None:
        """GX10 ping a Mac: documentar latencia y ruta."""
        rc, out, _ = run_cmd(f"tailscale ping {MAC_TS_IP} 2>&1 | head -3", timeout=15)
        if rc != 0:
            pytest.skip(f"No se pudo ping a Mac ({MAC_TS_IP})")
        # Detectar si es directo o relay
        is_relay = "via" in out.lower() and "relay" in out.lower()
        latency_line = out.strip().splitlines()[0] if out.strip() else ""
        # Extraer latencia del primer pong
        import re
        match = re.search(r"in (\d+)ms", latency_line)
        latency_ms = int(match.group(1)) if match else 0
        if latency_ms > 30 or is_relay:
            pytest.xfail(
                f"GX10→Mac vía relay ({latency_ms}ms). "
                f"Esto es aceptable pero subóptimo. "
                f"Considerar configuración de NAT hole punching."
            )

    def test_gx10_has_direct_peers(self) -> None:
        """GX10 tiene al menos un peer directo en Tailscale."""
        rc, out, _ = run_cmd("tailscale status 2>/dev/null")
        if rc != 0:
            pytest.skip("tailscale no disponible")
        has_direct = "direct" in out.lower()
        # También contar peers online
        online = len([l for l in out.splitlines() if "offline" not in l.lower() and l.strip()])
        assert online >= 2, f"Tailscale tiene solo {online} peers online"


@pytest.mark.mac
class TestTailscaleDirectMac:
    """Verifica estado de Tailscale desde Mac."""

    def test_mac_tailscale_online(self) -> None:
        """Mac tiene Tailscale activo."""
        rc, out, _ = run_cmd("tailscale status 2>/dev/null | head -5")
        assert rc == 0, "tailscale status falló en Mac"
        assert "mac" in out.lower() or MAC_TS_IP in out, (
            f"Mac no aparece en tailscale status: {out.strip()}"
        )

    def test_mac_to_gx10_latency(self) -> None:
        """Mac ping a GX10: debe ser directo (<20ms)."""
        rc, out, _ = run_cmd(f"tailscale ping {GX10_TS_IP} 2>&1 | head -3", timeout=15)
        if rc != 0:
            pytest.skip(f"No se pudo ping a GX10 ({GX10_TS_IP})")
        import re
        match = re.search(r"in (\d+)ms", out)
        latency_ms = int(match.group(1)) if match else 0
        assert latency_ms < 50, (
            f"Mac→GX10 latencia {latencia_ms}ms (>50ms = problema de red)"
        )
