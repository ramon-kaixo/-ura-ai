"""Tests de disponibilidad: verifica que servicios criticos estan activos y responden.

GX10: verifica servicios systemd y endpoints HTTP.
"""

from __future__ import annotations

import json

import pytest

from tests.infra.conftest import run_cmd


@pytest.mark.gx10
class TestServiceAvailability:
    """Verifica que servicios criticos estan activos."""

    @pytest.mark.parametrize(
        "service",
        [
            "opencode.service",
            "ollama.service",
            "tailscaled.service",
        ],
    )
    def test_service_active(self, service: str) -> None:
        _, out, _ = run_cmd(f"systemctl is-active {service}")
        assert out == "active", f"{service} no esta activo: {out}"

    def test_opencode_responds(self) -> None:
        rc, out, _ = run_cmd("curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/")
        if rc != 0:
            pytest.fail("OpenCode no responde en :8081")
        code = out.strip().strip("'")
        assert code in ("200", "401", "403"), f"OpenCode retorno HTTP {code}"

    def test_ollama_responds(self) -> None:
        rc, out, _ = run_cmd("curl -s http://localhost:11434/api/tags")
        if rc != 0:
            pytest.fail("Ollama no responde en :11434")
        data = json.loads(out)
        assert "models" in data, "Ollama api/tags no retorna campo models"


@pytest.mark.gx10
class TestServiceProcesses:
    """Verifica que procesos criticos estan corriendo."""

    def test_opencode_process_exists(self) -> None:
        rc, out, _ = run_cmd("pgrep -f opencode | head -5")
        assert rc == 0 and out.strip(), "Proceso opencode no encontrado"

    def test_ollama_process_exists(self) -> None:
        rc, out, _ = run_cmd("pgrep -f ollama | head -5")
        assert rc == 0 and out.strip(), "Proceso ollama no encontrado"

    def test_no_zombies(self) -> None:
        rc, out, _ = run_cmd("ps -eo stat | grep Z | wc -l")
        if rc != 0:
            pytest.skip("ps no disponible")
        zombie_count = int(out.strip()) if out.strip().isdigit() else 0
        assert zombie_count == 0, f"{zombie_count} zombies detectados"
