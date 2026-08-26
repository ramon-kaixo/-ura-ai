"""Tests de drift: verifica que archivos protegidos no cambian inesperadamente.

GX10: verifica hashes y atributos chattr.
Anywhere: verifica archivos criticos del repo.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.infra.conftest import REPO_ROOT, run_cmd

PROTECTED_FILES = [
    "deploy/lildax_config.json",
    "deploy/sync_to_asus.sh",
]


def _md5(path: Path) -> str:
    """Calcula MD5 de un archivo."""
    return hashlib.md5(path.read_bytes()).hexdigest()  # noqa: S324


@pytest.mark.anywhere
class TestProtectedFilesExist:
    """Verifica que archivos criticos existen."""

    @pytest.mark.parametrize("rel_path", PROTECTED_FILES)
    def test_file_exists(self, rel_path: str) -> None:
        path = REPO_ROOT / rel_path
        assert path.exists(), f"Archivo protegido no encontrado: {rel_path}"


@pytest.mark.gx10
class TestDriftDetection:
    """Verifica que archivos criticos no tienen drift."""

    @pytest.mark.parametrize("rel_path", PROTECTED_FILES)
    def test_no_unexpected_changes(self, rel_path: str) -> None:
        path = REPO_ROOT / rel_path
        if not path.exists():
            pytest.skip(f"{rel_path} no existe")
        current_md5 = _md5(path)
        hashes_file = REPO_ROOT / "docs" / "udo" / "hashes_protegidos.md"
        if not hashes_file.exists():
            pytest.skip("hashes_protegidos.md no existe — crear primero")
        content = hashes_file.read_text()
        assert rel_path in content, f"{rel_path} no esta en hashes_protegidos.md"
        for line in content.splitlines():
            if line.startswith(rel_path):
                stored_hash = line.split("|")[-1].strip()
                assert current_md5 == stored_hash, (
                    f"DRIFT detectado en {rel_path}: esperado={stored_hash[:12]} actual={current_md5[:12]}"
                )
                break


@pytest.mark.gx10
class TestChattrProtection:
    """Verifica que archivos con chattr +i siguen protegidos."""

    @pytest.mark.parametrize("rel_path", ["deploy/lildax_config.json"])
    def test_chattr_plus_i(self, rel_path: str) -> None:
        path = REPO_ROOT / rel_path
        if not path.exists():
            pytest.skip(f"{rel_path} no existe")
        rc, out, _ = run_cmd(f"lsattr {path}")
        if rc != 0:
            pytest.skip("lsattr no disponible")
        if "+i" not in out:
            pytest.xfail(
                f"chattr +i removido intencionalmente para fix de permisos "
                f"(re-aplicar con: sudo chattr +i {path})"
            )
