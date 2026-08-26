"""Tests de configuracion: valida JSONs, permisos, y archivos sensibles.

Anywhere: verifica JSONs del repo.
GX10: verifica permisos del sistema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from tests.infra.conftest import REPO_ROOT, run_cmd


@pytest.mark.anywhere
class TestRepoJSON:
    """Valida que los JSONs del repo son parseables."""

    @pytest.mark.parametrize(
        "json_path",
        [
            "deploy/system_manifest.json",
            "config/config.json",
        ],
    )
    def test_json_parseable(self, json_path: str) -> None:
        path = REPO_ROOT / json_path
        if not path.exists():
            pytest.skip(f"{json_path} no existe en esta maquina")
        with path.open() as f:
            data = json.load(f)
        assert isinstance(data, dict), f"{json_path} no es un dict"


@pytest.mark.anywhere
class TestNoBareIPs:
    """Verifica que no hay IPs hardcodeadas en el codigo fuente."""

    BARE_IPS: ClassVar[list[str]] = ["10.164.1.99", "192.168.1.135"]

    @pytest.mark.parametrize("ip", BARE_IPS)
    def test_no_bare_ip_in_source(self, ip: str) -> None:
        rc, out, _ = run_cmd(
            f'grep -rn "{ip}" motor/ core/ knowledge/ --include="*.py" --exclude-dir=__pycache__ --exclude-dir=.git',
            timeout=30,
        )
        assert rc != 0, f"IP bare encontrada en codigo fuente: {ip}\n{out}"


@pytest.mark.anywhere
class TestNoBackupsWithPasswords:
    """Verifica que no hay backups con contrasenas en el repo."""

    @pytest.mark.xfail(
        reason="Conocido: deploy/lildax_config.json.backup.20260825_000850 contiene password plaintext. "
        "Pendiente de eliminar en fase de seguridad (AUDITORIA-2026-08-26).",
        strict=True,
    )
    def test_no_password_backups(self) -> None:
        rc, out, _ = run_cmd(
            f'find {REPO_ROOT} -name "*backup*" '
            f'-not -path "*/__pycache__/*" -not -path "*/tests/*" '
            f'-exec grep -l "password\\|token\\|secret" {{}} \\; 2>/dev/null',
            timeout=30,
        )
        assert rc != 0, f"Backups con passwords encontrados:\n{out}"


@pytest.mark.gx10
class TestGX10SSHConfig:
    """Verifica la configuracion SSH de GX10."""

    def test_ssh_config_exists(self) -> None:
        config = Path.home() / ".ssh" / "config"
        assert config.exists(), "~/.ssh/config no encontrado"

    def test_ssh_config_has_hosts(self) -> None:
        config = Path.home() / ".ssh" / "config"
        if not config.exists():
            pytest.skip("SSH config no existe")
        content = config.read_text()
        expected_hosts = ["gx10", "gx10-lan", "gx10-ts"]
        found = [h for h in expected_hosts if f"Host {h}" in content]
        assert len(found) > 0, f"Ningun host encontrado en SSH config: {expected_hosts}"

    def test_ssh_keys_permits(self) -> None:
        ssh_dir = Path.home() / ".ssh"
        if not ssh_dir.exists():
            pytest.skip(".ssh no existe")
        for key in ssh_dir.glob("id_*"):
            if key.suffix == ".pub":
                continue
            mode = oct(key.stat().st_mode)[-3:]
            assert mode == "600", f"Clave privada {key.name} permisos {mode}, esperado 600"


@pytest.mark.gx10
class TestGX10SecretsEnv:
    """Verifica secrets.env en GX10."""

    def test_secrets_env_permits(self) -> None:
        secrets = Path("/etc/ura/secrets.env")
        if not secrets.exists():
            pytest.skip("secrets.env no existe")
        mode = oct(secrets.stat().st_mode)[-3:]
        assert mode == "600", f"secrets.env permisos {mode}, esperado 600"

    def test_secrets_env_in_gitignore(self) -> None:
        gitignore = REPO_ROOT / ".gitignore"
        if not gitignore.exists():
            pytest.skip(".gitignore no existe")
        content = gitignore.read_text()
        assert "secrets.env" in content, "secrets.env no esta en .gitignore"
