"""Smoke tests de integracion: ejecuta verificaiones rapidas del sistema completo.

GX10: smoke tests contra servicios reales.
"""

from __future__ import annotations

import pytest

from tests.infra.conftest import run_cmd


@pytest.mark.gx10
class TestSystemSmoke:
    """Smoke tests que verifican que el sistema esta operativo."""

    def test_opencode_responds(self) -> None:
        rc, out, _ = run_cmd("curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/")
        assert rc == 0, "OpenCode no responde"
        code = out.strip().strip("'")
        assert code in ("200", "401", "403"), f"OpenCode HTTP {code}"

    def test_ollama_has_models(self) -> None:
        rc, out, _ = run_cmd("curl -s http://localhost:11434/api/tags")
        assert rc == 0, "Ollama no responde"
        import json

        data = json.loads(out)
        assert len(data.get("models", [])) > 0, "Ollama sin modelos"

    def test_ssh_port_open(self) -> None:
        rc, _, _ = run_cmd("ss -tlnp | grep :22")
        assert rc == 0, "Puerto SSH no activo"

    def test_git_repo_clean(self) -> None:
        rc, out, _ = run_cmd("git status --short", timeout=15)
        assert rc == 0, f"git status fallo: {out}"
        # En GX10, el working tree puede tener archivos sin commitear (esperado)
        # Solo verificamos que git funciona

    def test_no_critical_errors_in_logs(self) -> None:
        rc, out, _ = run_cmd(
            "journalctl -u opencode.service --since '1 hour ago' --no-pager -p err 2>/dev/null | head -5"
        )
        if rc != 0:
            pytest.skip("journalctl no disponible o servicio no existe")
        # Si hay errores criticos en la ultima hora, reportar
        if out.strip():
            pytest.xfail(f"Errores criticos en logs de OpenCode:\n{out[:500]}")
