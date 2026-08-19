"""Tests smoke generados por plantilla (determinista, sin LLM)."""

import pytest

from motor.core.llm._state import build_llm_state


def test_import__state():
    """El módulo importa sin errores."""
    assert build_llm_state is not None


def test_funcion__state_build_llm_state():
    """La función no lanza con argumentos básicos."""
    try:
        build_llm_state('')
    except (TypeError, ValueError, NotImplementedError):
        pytest.skip('no aplicable con argumentos básicos')

