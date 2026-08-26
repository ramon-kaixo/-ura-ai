"""Tests de rendimiento: verifica latencia basica de servicios.

GX10: mide tiempo de respuesta de endpoints.
"""

from __future__ import annotations

import pytest

from tests.infra.conftest import run_cmd


@pytest.mark.gx10
class TestEndpointLatency:
    """Mide latencia basica de endpoints HTTP."""

    def test_opencode_latency(self) -> None:
        rc, out, _ = run_cmd(
            "curl -s -o /dev/null -w '%{time_total}' http://localhost:8081/",
            timeout=15,
        )
        if rc != 0:
            pytest.skip("OpenCode no disponible")
        latency = float(out.strip().strip("'"))
        assert latency < 2.0, f"OpenCode latencia太高: {latency:.2f}s (max 2s)"

    def test_ollama_latency(self) -> None:
        rc, out, _ = run_cmd(
            "curl -s -o /dev/null -w '%{time_total}' http://localhost:11434/api/tags",
            timeout=15,
        )
        if rc != 0:
            pytest.skip("Ollama no disponible")
        latency = float(out.strip().strip("'"))
        assert latency < 2.0, f"Ollama latencia太高: {latency:.2f}s (max 2s)"

    def test_opencode_concurrent_requests(self) -> None:
        """Verifica que OpenCode maneja 5 requests secuenciales sin degradacion."""
        latencies = []
        for _ in range(5):
            rc, out, _ = run_cmd(
                "curl -s -o /dev/null -w '%{time_total}' http://localhost:8081/",
                timeout=15,
            )
            if rc != 0:
                pytest.skip("OpenCode no disponible")
            latencies.append(float(out.strip().strip("'")))
        avg = sum(latencies) / len(latencies)
        assert avg < 2.0, f"Promedio latencia太高: {avg:.2f}s"
        assert max(latencies) < 5.0, f"Latencia max太高: {max(latencies):.2f}s"
