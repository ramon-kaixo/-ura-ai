"""Tests de compliance: verifica permisos, .gitignore, y ausencia de secretos expuestos.

Anywhere: verifica el repo.
GX10: verifica permisos del sistema.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from tests.infra.conftest import REPO_ROOT, run_cmd


@pytest.mark.anywhere
class TestNoWorldWritable:
    """Verifica que no hay archivos con permisos 777 en el repo."""

    def test_no_777_files(self) -> None:
        rc, out, _ = run_cmd(
            f"find {REPO_ROOT} -type f -perm 777 "
            f"-not -path '*/.git/*' -not -path '*/__pycache__/*' "
            f"-not -path '*/.venv/*' 2>/dev/null",
            timeout=30,
        )
        assert rc != 0 or not out.strip(), f"Archivos 777 encontrados:\n{out}"


@pytest.mark.anywhere
class TestGitignoreCoverage:
    """Verifica que archivos sensibles estan en .gitignore."""

    SENSITIVE_PATTERNS: ClassVar[list[str]] = ["secrets.env", ".env"]

    def test_gitignore_exists(self) -> None:
        assert (REPO_ROOT / ".gitignore").exists()

    @pytest.mark.parametrize("pattern", SENSITIVE_PATTERNS)
    def test_sensitive_in_gitignore(self, pattern: str) -> None:
        gitignore = REPO_ROOT / ".gitignore"
        content = gitignore.read_text()
        assert pattern in content, f"{pattern} no esta en .gitignore"


@pytest.mark.anywhere
class TestNoHardcodedSecrets:
    """Busca secretos hardcodeados en el codigo fuente."""

    @pytest.mark.parametrize(
        "pattern",
        [
            "password\\s*=\\s*['\"][^'\"$]",
            "api_key\\s*=\\s*['\"][^'\"$]",
            "token\\s*=\\s*['\"][^'\"$]",
        ],
    )
    def test_no_hardcoded_secrets(self, pattern: str) -> None:
        rc, out, _ = run_cmd(
            f'grep -rn "{pattern}" motor/ core/ knowledge/ --include="*.py" --exclude-dir=__pycache__ 2>/dev/null',
            timeout=30,
        )
        if rc == 0 and out.strip():
            lines = [l for l in out.splitlines() if "#" not in l.split(":")[2][:5]]
            assert not lines, "Posibles secretos hardcodeados:\n" + "\n".join(lines[:10])


@pytest.mark.gx10
class TestGX10Compliance:
    """Verificaciones especificas de GX10."""

    def test_no_nopasswd_sudo(self) -> None:
        rc, out, _ = run_cmd(
            'grep -r "NOPASSWD" /etc/sudoers.d/ 2>/dev/null',
        )
        if rc == 0 and out.strip():
            pytest.fail(f"NOPASSWD detectado en sudoers:\n{out}")

    def test_deploy_config_permits(self) -> None:
        config = REPO_ROOT / "deploy" / "lildax_config.json"
        if not config.exists():
            pytest.skip("lildax_config.json no existe")
        mode = oct(config.stat().st_mode)[-3:]
        assert mode == "600", f"lildax_config.json permisos {mode}, esperado 600"
