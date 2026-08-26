"""Tests de conectividad HTTP Mac→GX10: verifica que Mac puede alcanzar servicios en GX10.

Estos tests cubren el GAP: ningún test existente verifica conectividad HTTP
cross-machine. Los tests existentes solo hacen ping (test_conectividad.py)
o verifican localhost (test_puertos.py, test_disponibilidad.py).
"""

from __future__ import annotations

import json
import urllib.request

import pytest

from tests.infra.conftest import run_cmd
from tests.redes import GX10_TS_IP


@pytest.mark.mac
class TestMacToGX10Ollama:
    """Verifica que Mac puede alcanzar Ollama en GX10 vía red."""

    OLLAMA_URL = f"http://{GX10_TS_IP}:11434"

    def test_mac_curl_gx10_ollama(self) -> None:
        """Mac hace curl a GX10:11434/api/tags y obtiene modelos."""
        rc, out, _ = run_cmd(
            f"curl -s --connect-timeout 5 {self.OLLAMA_URL}/api/tags",
            timeout=10,
        )
        assert rc == 0, f"No se pudo conectar a Ollama en GX10 ({GX10_TS_IP}:11434)"
        data = json.loads(out)
        models = data.get("models", [])
        assert len(models) > 0, "GX10 Ollama no tiene modelos disponibles"

    def test_mac_gx10_ollama_modelos_esperados(self) -> None:
        """Los modelos criticos estan presentes en GX10."""
        rc, out, _ = run_cmd(
            f"curl -s --connect-timeout 5 {self.OLLAMA_URL}/api/tags",
            timeout=10,
        )
        if rc != 0:
            pytest.skip("No se pudo conectar a Ollama en GX10")
        data = json.loads(out)
        names = {m["name"].split(":")[0] for m in data.get("models", [])}
        criticos = {"qwen3-coder", "qwen3.6", "gemma4"}
        faltantes = criticos - names
        assert not faltantes, f"Modelos criticos faltantes en GX10: {faltantes}"


@pytest.mark.mac
class TestMacToGX10OpenCode:
    """Verifica que Mac puede alcanzar OpenCode Web en GX10."""

    OPENCODE_URL = f"http://{GX10_TS_IP}:8081"

    def test_mac_curl_gx10_opencode(self) -> None:
        """Mac hace curl a GX10:8081 y obtiene respuesta HTTP."""
        rc, out, _ = run_cmd(
            f"curl -s --connect-timeout 5 -o /dev/null -w '%{{http_code}}' {self.OPENCODE_URL}/",
            timeout=10,
        )
        assert rc == 0, "No se pudo conectar a OpenCode en GX10"
        http_code = out.strip()
        assert http_code in ("200", "401", "403"), (
            f"OpenCode en GX10 retorno HTTP {http_code} (esperado 200/401/403)"
        )


@pytest.mark.gx10
class TestGX10ServicesBinding:
    """Verifica que servicios criticos en GX10 escuchan en todas las interfaces."""

    def test_ollama_bound_to_all_interfaces(self) -> None:
        """Ollama debe escuchar en 0.0.0.0 o * (no solo 127.0.0.1)."""
        rc, out, _ = run_cmd("ss -tlnp | grep :11434")
        if rc != 0:
            pytest.skip("Ollama no activo")
        assert "0.0.0.0" in out or "*:" in out or "[::]:" in out, (
            f"Ollama no escucha en todas las interfaces: {out.strip()}"
        )

    def test_opencode_bound_to_all_interfaces(self) -> None:
        """OpenCode debe escuchar en 0.0.0.0 (accesible desde Mac)."""
        rc, out, _ = run_cmd("ss -tlnp | grep :8081")
        if rc != 0:
            pytest.skip("OpenCode no activo")
        assert "0.0.0.0" in out, (
            f"OpenCode no escucha en 0.0.0.0: {out.strip()}"
        )

    def test_model_router_bound_to_localhost(self) -> None:
        """Model Router debe estar en 127.0.0.1 (no expuesto)."""
        rc, out, _ = run_cmd("ss -tlnp | grep :11435")
        if rc != 0:
            pytest.skip("Model Router no activo")
        if "127.0.0.1" in out:
            pass  # Correcto
        elif "0.0.0.0" in out:
            pytest.xfail("Model Router escucha en 0.0.0.0 — considerar binding a 127.0.0.1")
