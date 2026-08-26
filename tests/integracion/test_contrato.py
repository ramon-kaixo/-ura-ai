"""Tests de integracion: verifica contratos entre componentes y smoke tests.

Anywhere: smoke tests basicos del repo.
GX10: verifica contratos de API con servicios reales.
"""

from __future__ import annotations

import json

import pytest

from tests.infra.conftest import REPO_ROOT, run_cmd


@pytest.mark.anywhere
class TestRepoSmoke:
    """Smoke tests basicos del repo."""

    def test_import_motor(self) -> None:
        rc, out, _ = run_cmd("python3 -c 'import motor; print(\"ok\")'")
        assert rc == 0, f"motor no es importable: {out}"

    def test_import_core(self) -> None:
        rc, out, _ = run_cmd("python3 -c 'import core; print(\"ok\")'")
        assert rc == 0, f"core no es importable: {out}"

    def test_import_knowledge(self) -> None:
        rc, out, _ = run_cmd("python3 -c 'import knowledge; print(\"ok\")'")
        assert rc == 0, f"knowledge no es importable: {out}"

    def test_pyproject_parseable(self) -> None:
        import tomllib

        with (REPO_ROOT / "pyproject.toml").open("rb") as f:
            data = tomllib.load(f)
        assert "project" in data, "pyproject.toml no tiene seccion [project]"


@pytest.mark.gx10
class TestAPIContract:
    """Verifica que los APIs responden con contratos validos."""

    def test_ollama_api_tags_contract(self) -> None:
        rc, out, _ = run_cmd("curl -s http://localhost:11434/api/tags")
        if rc != 0:
            pytest.skip("Ollama no disponible")
        data = json.loads(out)
        assert "models" in data, "api/tags no tiene campo 'models'"
        if data["models"]:
            model = data["models"][0]
            assert "name" in model, "Modelo no tiene campo 'name'"
            assert "size" in model, "Modelo no tiene campo 'size'"

    def test_opencode_health_contract(self) -> None:
        rc, out, _ = run_cmd("curl -s http://localhost:8081/health 2>/dev/null")
        if rc != 0:
            pytest.skip("OpenCode no disponible")
        if out.strip():
            try:
                data = json.loads(out)
                assert "status" in data or "ok" in data, "Health endpoint no retorna status"
            except json.JSONDecodeError:
                pytest.xfail("Health endpoint no retorna JSON (puede ser HTML de auth)")

    def test_opencode_api_v1_status(self) -> None:
        rc, out, _ = run_cmd("curl -s http://localhost:8081/api/v1/status 2>/dev/null")
        if rc != 0:
            pytest.skip("OpenCode no disponible")
        if out.strip():
            try:
                data = json.loads(out)
                assert isinstance(data, dict), "api/v1/status no retorna dict"
            except json.JSONDecodeError:
                pytest.xfail("api/v1/status no retorna JSON")


@pytest.mark.anywhere
class TestKnowledgeEngineCLI:
    """Verifica que el CLI de Knowledge Engine funciona."""

    def test_ke_cli_help(self) -> None:
        rc, out, _ = run_cmd("python3 -m knowledge.engine.cli --help")
        assert rc == 0, f"KE CLI --help fallo: {out}"
        assert "knowledge" in out.lower() or "usage" in out.lower(), f"KE CLI output inesperado: {out[:200]}"
