"""Tests de aprovisionamiento: verifica que servicios y directorios criticos existen.

SoloGX10: verifica servicios systemd.
Anywhere: verifica estructura del repo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.infra.conftest import REPO_ROOT, run_cmd


@pytest.mark.anywhere
class TestRepoStructure:
    """Verifica que la estructura basica del repo existe."""

    @pytest.mark.parametrize(
        "dir_name",
        [
            "motor",
            "core",
            "tests",
            "scripts",
            "config",
            "deploy",
            "docs",
        ],
    )
    def test_critical_directories_exist(self, dir_name: str) -> None:
        path = REPO_ROOT / dir_name
        assert path.exists(), f"Directorio critico no encontrado: {dir_name}"

    def test_pyproject_toml_exists(self) -> None:
        assert (REPO_ROOT / "pyproject.toml").exists()

    def test_requirements_txt_exists(self) -> None:
        assert (REPO_ROOT / "requirements.txt").exists()

    def test_venv_exists(self) -> None:
        venv = REPO_ROOT / ".venv"
        assert venv.exists(), ".venv no encontrado"

    def test_venv_has_pytest(self) -> None:
        pytest_bin = REPO_ROOT / ".venv" / "bin" / "pytest"
        if not pytest_bin.exists():
            pytest_bin = REPO_ROOT / ".venv" / "Scripts" / "pytest.exe"
        assert pytest_bin.exists(), "pytest no encontrado en .venv"


@pytest.mark.gx10
class TestGX10Services:
    """Verifica que servicios criticos de GX10 existen."""

    @pytest.mark.parametrize(
        "service",
        [
            "opencode.service",
            "ollama.service",
            "tailscaled.service",
        ],
    )
    def test_systemd_service_exists(self, service: str) -> None:
        rc, out, _ = run_cmd(f"systemctl list-unit-files {service} --no-legend")
        assert rc == 0 and service in out, f"Servicio no encontrado: {service}"

    def test_opencode_service_active(self) -> None:
        _, out, _ = run_cmd("systemctl is-active opencode.service")
        assert out == "active", f"opencode no esta activo: {out}"

    def test_ollama_service_active(self) -> None:
        _, out, _ = run_cmd("systemctl is-active ollama.service")
        assert out == "active", f"ollama no esta activo: {out}"


@pytest.mark.gx10
class TestGX10Directories:
    """Verifica directorios criticos de GX10."""

    def test_ura_config_dir(self) -> None:
        assert Path("/etc/ura").exists(), "/etc/ura no encontrado"

    def test_ura_secrets_env(self) -> None:
        secrets = Path("/etc/ura/secrets.env")
        assert secrets.exists(), "/etc/ura/secrets.env no encontrado"

    def test_ura_secrets_permits(self) -> None:
        secrets = Path("/etc/ura/secrets.env")
        if secrets.exists():
            mode = oct(secrets.stat().st_mode)[-3:]
            assert mode == "600", f"secrets.env permisos {mode}, esperado 600"
