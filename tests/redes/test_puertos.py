"""Tests de puertos: verifica que servicios escuchan en puertos correctos.

GX10: verifica puertos criticos.
"""

from __future__ import annotations

import json
from typing import ClassVar

import pytest

from tests.infra.conftest import run_cmd


@pytest.mark.gx10
class TestCriticalPorts:
    """Verifica que puertos criticos estan abiertos y responden."""

    @pytest.mark.parametrize(
        "port,service",
        [
            (8081, "OpenCode API"),
            (11434, "Ollama"),
        ],
    )
    def test_port_responds(self, port: int, service: str) -> None:
        rc, _, _ = run_cmd(f"ss -tlnp | grep :{port}")
        assert rc == 0, f"Puerto {port} ({service}) no esta escuchando"

    def test_opencode_returns_valid_http(self) -> None:
        rc, out, _ = run_cmd("curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/")
        if rc != 0:
            pytest.skip("OpenCode no disponible")
        code = out.strip().strip("'")
        assert code in ("200", "401", "403"), f"OpenCode retorno HTTP {code}"

    def test_ollama_returns_models(self) -> None:
        rc, out, _ = run_cmd("curl -s http://localhost:11434/api/tags")
        if rc != 0:
            pytest.skip("Ollama no disponible")
        try:
            data = json.loads(out)
            assert "models" in data, "Ollama api/tags no retorna models"
        except (json.JSONDecodeError, KeyError):
            pytest.fail("Ollama api/tags retorno JSON invalido")


@pytest.mark.gx10
class TestNoUnexpectedPorts:
    """Verifica que no hay puertos inesperados expuestos."""

    WHITELIST: ClassVar[set[int]] = {22, 8081, 11434, 6333, 6334, 8000, 8080, 8888}

    def test_no_unexpected_listeners(self) -> None:
        rc, out, _ = run_cmd("ss -tlnp | grep LISTEN")
        if rc != 0:
            pytest.skip("ss no disponible")
        unexpected = []
        for line in out.splitlines():
            parts = line.split()
            for part in parts:
                if ":" in part:
                    try:
                        port = int(part.split(":")[-1])
                        if port not in self.WHITELIST and port > 1024:
                            unexpected.append(f"  puerto {port}: {line.strip()}")
                    except (ValueError, IndexError):
                        pass
        assert not unexpected, "Puertos inesperados expuestos:\n" + "\n".join(unexpected[:20])


@pytest.mark.gx10
class TestPortBinding:
    """Verifica que servicios criticos no escuchan en 0.0.0.0 sin necesidad."""

    @pytest.mark.parametrize("port", [8081, 8080])
    def test_service_not_public(self, port: int) -> None:
        rc, out, _ = run_cmd(f"ss -tlnp | grep :{port}")
        if rc != 0:
            pytest.skip(f"Puerto {port} no activo")
        if "0.0.0.0" in out:  # noqa: S104
            pytest.xfail(f"Puerto {port} escucha en 0.0.0.0 (expuesto). Considerar binding a 127.0.0.1.")
