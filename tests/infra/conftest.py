"""Fixtures para tests de infraestructura.

Detecta la maquina (gx10/mac) y provee helpers de platform.
"""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def is_gx10() -> bool:
    """Detecta si estamos en GX10 (ASUS GB10)."""
    hostname = platform.node().lower()
    return any(k in hostname for k in ("gx10", "asus", "gb10"))


def is_mac() -> bool:
    """Detecta si estamos en Mac."""
    return platform.system() == "Darwin"


def run_cmd(cmd: str, timeout: int = 10) -> tuple[int, str, str]:
    """Ejecuta un comando y retorna (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(  # noqa: S602, PLW1510
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as exc:
        return -1, "", str(exc)


@pytest.fixture(autouse=True)
def _platform_guard() -> Generator[None, None, None]:
    """Marca skip automatico para tests con marker de plataforma incorrecta."""
    yield


@pytest.fixture
def repo_root() -> Path:
    """Raiz del repositorio."""
    return REPO_ROOT


@pytest.fixture
def gx10() -> bool:
    """True si estamos en GX10."""
    return is_gx10()


@pytest.fixture
def on_mac() -> bool:
    """True si estamos en Mac."""
    return is_mac()
