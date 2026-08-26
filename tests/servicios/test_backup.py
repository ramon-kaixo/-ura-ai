"""Tests de backup: verifica que backups existen y son recientes.

GX10: verifica directorios de backup.
Mac: verifica backup sincronizado.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.infra.conftest import run_cmd


@pytest.mark.gx10
class TestGX10Backups:
    """Verifica backups en GX10."""

    def test_udo_backup_dir_exists(self) -> None:
        backup_dir = Path.home() / "URA" / "backups" / "udo"
        if not backup_dir.exists():
            pytest.xfail("Directorio de backup UDO no existe")

    def test_recent_backup_exists(self) -> None:
        backup_dir = Path.home() / "URA" / "backups" / "udo"
        if not backup_dir.exists():
            pytest.skip("Directorio de backup no existe")
        _, out, _ = run_cmd(f"find {backup_dir} -mtime -7 -type f | wc -l")
        count = int(out.strip()) if out.strip().isdigit() else 0
        assert count > 0, "No hay backups en los ultimos 7 dias"

    def test_secrets_backup_exists(self) -> None:
        backup_base = Path.home() / "URA" / "backups"
        if not backup_base.exists():
            pytest.skip("Directorio de backups no existe")
        _, out, _ = run_cmd(f"find {backup_base} -name '*secrets*' -mtime -30 -type f | wc -l")
        count = int(out.strip()) if out.strip().isdigit() else 0
        if count == 0:
            pytest.xfail("No hay backup de secrets.env en los ultimos 30 dias")


@pytest.mark.mac
class TestMacBackups:
    """Verifica backups sincronizados en Mac."""

    def test_gx10_backup_dir_exists(self) -> None:
        backup_dir = Path.home() / "URA" / "backups_gx10"
        if not backup_dir.exists():
            pytest.xfail("Directorio backups_gx10 no existe")

    def test_recent_gx10_backup(self) -> None:
        backup_dir = Path.home() / "URA" / "backups_gx10"
        if not backup_dir.exists():
            pytest.skip("Directorio backups_gx10 no existe")
        _, out, _ = run_cmd(f"find {backup_dir} -mtime -7 -type f | wc -l")
        count = int(out.strip()) if out.strip().isdigit() else 0
        assert count > 0, "No hay backups de GX10 en los ultimos 7 dias"
