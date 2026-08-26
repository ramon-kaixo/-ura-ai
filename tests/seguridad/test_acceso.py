"""Tests de acceso: verifica permisos de archivos criticos del sistema.

GX10: verifica permisos de SSH, secrets, configs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.infra.conftest import run_cmd


@pytest.mark.gx10
class TestSSHPermissions:
    """Verifica permisos de archivos SSH en GX10."""

    def test_ssh_dir_permits(self) -> None:
        ssh_dir = Path.home() / ".ssh"
        if not ssh_dir.exists():
            pytest.skip(".ssh no existe")
        mode = oct(ssh_dir.stat().st_mode)[-3:]
        assert mode == "700", f".ssh permisos {mode}, esperado 700"

    def test_authorized_keys_permits(self) -> None:
        ak = Path.home() / ".ssh" / "authorized_keys"
        if not ak.exists():
            pytest.skip("authorized_keys no existe")
        mode = oct(ak.stat().st_mode)[-3:]
        assert mode == "644", f"authorized_keys permisos {mode}, esperado 644"

    def test_private_keys_permits(self) -> None:
        ssh_dir = Path.home() / ".ssh"
        if not ssh_dir.exists():
            pytest.skip(".ssh no existe")
        bad_keys = []
        for key in ssh_dir.glob("id_*"):
            if key.suffix == ".pub":
                continue
            mode = oct(key.stat().st_mode)[-3:]
            if mode != "600":
                bad_keys.append(f"{key.name}: {mode}")
        assert not bad_keys, "Claves privadas con permisos incorrectos:\n" + "\n".join(bad_keys)


@pytest.mark.gx10
class TestSecretsPermissions:
    """Verifica permisos de archivos con secretos."""

    def test_secrets_env_permits(self) -> None:
        secrets = Path("/etc/ura/secrets.env")
        if not secrets.exists():
            pytest.skip("secrets.env no existe")
        mode = oct(secrets.stat().st_mode)[-3:]
        assert mode == "600", f"secrets.env permisos {mode}, esperado 600"

    def test_lildax_config_permits(self) -> None:
        from tests.infra.conftest import REPO_ROOT

        config = REPO_ROOT / "deploy" / "lildax_config.json"
        if not config.exists():
            pytest.skip("lildax_config.json no existe")
        mode = oct(config.stat().st_mode)[-3:]
        assert mode == "600", f"lildax_config.json permisos {mode}, esperado 600"


@pytest.mark.gx10
class TestNoWorldReadableSecrets:
    """Verifica que no hay archivos de secretos legibles por otros usuarios."""

    def test_no_world_readable_env_files(self) -> None:
        rc, out, _ = run_cmd(
            'find /etc/ura -name "*.env" -perm -o=r 2>/dev/null',
        )
        if rc == 0 and out.strip():
            pytest.fail(f"Archivos .env legibles por otros:\n{out}")
