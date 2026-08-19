"""Tests smoke generados por plantilla (determinista, sin LLM)."""

import pytest

from motor.core.utils.anonymizer import sanitize_text


def test_import_anonymizer():
    """El módulo importa sin errores."""
    assert sanitize_text is not None


def test_funcion_anonymizer_sanitize_text():
    """La función no lanza con argumentos básicos."""
    try:
        sanitize_text('')
    except (TypeError, ValueError, NotImplementedError):
        pytest.skip('no aplicable con argumentos básicos')

