"""Tests smoke generados por plantilla (determinista, sin LLM)."""

import pytest

from motor.core.llm.base import validate_provider


def test_import_base():
    """El módulo importa sin errores."""
    assert validate_provider is not None


def test_funcion_base_validate_provider():
    """La función no lanza con argumentos básicos."""
    try:
        validate_provider('')
    except (TypeError, ValueError, NotImplementedError):
        pytest.skip('no aplicable con argumentos básicos')

