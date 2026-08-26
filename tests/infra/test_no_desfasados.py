"""Tests de limpieza: verifica que no hay referencias a modelos/IPs desfasados.

Detecta código que apunta a modelos eliminados, IPs muertas, o backups
con credenciales en el repo.
"""

from __future__ import annotations

import re

import pytest

from tests.infra.conftest import REPO_ROOT, run_cmd

# Modelos que ya NO existen en GX10 (eliminados o reemplazados)
MODELOS_MUERTOS = ["qwen2.5-coder:14b", "qwen2.5-coder:32b", "qwen2.5:3b", "llama3.2:3b", "gemma:2b"]

# IPs que ya no son válidas (Ethernet sin carrier desde 2026-08-24)
IPS_MUERTAS = ["10.164.1.99", "192.168.1.135"]


@pytest.mark.anywhere
class TestNoModelosDesfasados:
    """Verifica que no hay referencias a modelos eliminados en código activo."""

    @pytest.mark.parametrize("modelo", MODELOS_MUERTOS)
    def test_no_modelo_en_motor_core(self, modelo: str) -> None:
        """Modelos muertos no deben estar hardcodeados en motor/ o core/."""
        rc, out, _ = run_cmd(
            f"grep -rn '{modelo}' motor/ core/ --include='*.py' 2>/dev/null "
            f"| grep -v __pycache__ | grep -v build/ | grep -v test_",
            timeout=15,
        )
        if rc != 0:
            return  # grep no encontró nada — correcto
        # Filtrar líneas que son configuración por defecto (aceptable) vs uso directo
        lines = [l for l in out.strip().splitlines() if l.strip()]
        # Permitir solo en configuración (default=, fallback=, etc.)
        hardcoded = [
            l for l in lines
            if not re.search(r"(default|fallback|env|argparse|.MODELO|_MODEL)", l, re.IGNORECASE)
        ]
        assert not hardcoded, (
            f"Modelo muerto '{modelo}' hardcodeado en código funcional:\n"
            + "\n".join(hardcoded[:5])
        )


@pytest.mark.anywhere
class TestNoIPsMuertas:
    """Verifica que no hay IPs obsoletas en scripts/pro/."""

    @pytest.mark.parametrize("ip", IPS_MUERTAS)
    def test_no_ip_muerta_en_scripts(self, ip: str) -> None:
        """IPs muertas no deben estar en scripts/pro/."""
        rc, out, _ = run_cmd(
            f"grep -rn '{ip}' scripts/pro/ --include='*.py' --include='*.sh' "
            f"2>/dev/null | grep -v __pycache__ | grep -v parse_pytest",
            timeout=15,
        )
        if rc != 0:
            return
        lines = [l for l in out.strip().splitlines() if l.strip()]
        # Permitir solo en comentarios o docs
        active = [l for l in lines if not l.strip().startswith("#")]
        assert not active, (
            f"IP muerta '{ip}' encontrada en scripts/pro/:\n"
            + "\n".join(active[:5])
        )


@pytest.mark.anywhere
class TestNoBackupsConPassword:
    """Verifica que no hay archivos .backup con passwords en el repo."""

    def test_no_backup_files_in_repo(self) -> None:
        """No debe haber archivos .backup.* tracked por git."""
        rc, out, _ = run_cmd(
            "git ls-files '*.backup.*' 'backups_gx10/*.backup.*' 2>/dev/null",
            timeout=10,
        )
        if rc != 0:
            return
        files = [f for f in out.strip().splitlines() if f.strip()]
        assert not files, (
            f"Archivos .backup tracked por git: {files[:5]}"
        )


@pytest.mark.anywhere
class TestBuildDirNotTracked:
    """Verifica que build/ no está tracked por git."""

    def test_build_not_in_git(self) -> None:
        """build/ no debe estar en el índice de git."""
        rc, out, _ = run_cmd("git ls-files build/ 2>/dev/null", timeout=10)
        files = [f for f in out.strip().splitlines() if f.strip()]
        assert not files, (
            f"build/ está tracked por git ({len(files)} archivos). "
            f"Agregar a .gitignore y rm -r build/"
        )
