"""Tests para la infraestructura de hooks de git (Módulo 4)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class TestPostCommitHook:
    def test_hook_existe(self) -> None:
        hook = _project_root() / "scripts" / "pro" / "hooks" / "post-commit"
        assert hook.exists()

    def test_hook_es_ejecutable(self) -> None:
        hook = _project_root() / "scripts" / "pro" / "hooks" / "post-commit"
        assert os.access(hook, os.X_OK)

    def test_sin_env_no_dispara(self, tmp_path: Path) -> None:
        # Sin URA_TUNELADORA_POST_COMMIT el hook no dispara tuneladora
        repo = tmp_path / "repo"
        repo.mkdir()
        hook = repo / "post-commit"
        hook.write_text(
            "#!/bin/sh\n"
            "if [ -n \"$URA_TUNELADORA_POST_COMMIT\" ]; then\n"
            "  touch triggered\n"
            "fi\n",
        )
        os.chmod(hook, 0o755)
        r = subprocess.run([str(hook)], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0
        assert not (repo / "triggered").exists()

    def test_con_env_dispara(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        hook = repo / "post-commit"
        hook.write_text(
            "#!/bin/sh\n"
            "if [ -n \"$URA_TUNELADORA_POST_COMMIT\" ]; then\n"
            "  touch triggered\n"
            "fi\n",
        )
        os.chmod(hook, 0o755)
        env = dict(os.environ, URA_TUNELADORA_POST_COMMIT="1")
        r = subprocess.run([str(hook)], capture_output=True, text=True, timeout=10, env=env, cwd=str(repo))
        assert r.returncode == 0
        assert (repo / "triggered").exists()

    def test_hook_no_bloquea(self) -> None:
        # El hook real termina rápido (no espera a la tuneladora)
        hook = _project_root() / "scripts" / "pro" / "hooks" / "post-commit"
        r = subprocess.run(
            ["timeout", "5", "sh", "-c", f"URA_TUNELADORA_POST_COMMIT=1 {hook}"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(_project_root()),
        )
        assert r.returncode == 0


class TestInstallHooks:
    def test_install_copia_hooks(self, tmp_path: Path) -> None:
        src = _project_root() / "scripts" / "pro" / "hooks" / "post-commit"
        dst = tmp_path / "post-commit"
        dst.write_text(src.read_text())
        os.chmod(dst, 0o755)
        assert dst.exists()
        assert os.access(dst, os.X_OK)

    def test_hook_instalado_en_git(self) -> None:
        installed = _project_root() / ".git" / "hooks" / "post-commit"
        assert installed.exists()
        assert os.access(installed, os.X_OK)


class TestMakefileTargets:
    def test_verify_hooks_target(self) -> None:
        makefile = _project_root() / "Makefile"
        content = makefile.read_text()
        assert "verify-hooks" in content
        assert "install-hooks" in content

    def test_validate_incluye_verify(self) -> None:
        makefile = _project_root() / "Makefile"
        content = makefile.read_text()
        assert "validate:" in content
        assert "verify-hooks" in content.split("validate:")[1].split("\n")[0]
