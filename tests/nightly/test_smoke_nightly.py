"""Smoke tests para tests/nightly/ — verifica que los archivos no están rotos.

Ejecución rápida (<10s) que confirma:
1. Los archivos de test son importables (sintaxis OK)
2. Los scripts CLI referenciados existen
3. Los módulos testeados son importables

No ejecuta los tests nightly completos (eso es para pipelines programadas).
"""
from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

NIGHTLY_DIR = Path(__file__).resolve().parent
REPO_ROOT = NIGHTLY_DIR.parent.parent
TEST_FILES = sorted(NIGHTLY_DIR.glob("test_*.py"))


@pytest.mark.parametrize(
    "test_file",
    TEST_FILES,
    ids=[t.stem for t in TEST_FILES],
)
def test_nightly_file_parses(test_file: Path) -> None:
    """El archivo de test debe ser Python válido (parseable por ast)."""
    source = test_file.read_text(encoding="utf-8")
    ast.parse(source, filename=str(test_file))


def test_knowledge_engine_cli_exists() -> None:
    """El CLI de knowledge.engine debe ser invocable."""
    result = subprocess.run(
        [sys.executable, "-m", "knowledge.engine.cli", "--help"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=10,
    )
    assert result.returncode == 0, f"knowledge.engine.cli --help falló: {result.stderr[:200]}"
    assert "init" in result.stdout or "Knowledge" in result.stdout


@pytest.mark.parametrize(
    "module_path",
    [
        "motor.plugin.base",
        "motor.plugin.registry",
        "motor.core.config",
        "motor.exceptions",
    ],
)
def test_critical_modules_importable(module_path: str) -> None:
    """Los módulos críticos testeados por nightly deben ser importables."""
    mod = importlib.import_module(module_path)
    assert mod is not None
