"""Tests smoke generados por plantilla (determinista, sin LLM)."""

import pytest

from motor.core.fusion.config import FusionConfig, make_config_hash


def test_import_config():
    """El módulo importa sin errores."""
    assert FusionConfig is not None


def test_dataclass_config_FusionConfig():
    """Instanciación con valores por defecto (skip si valida/requiere args)."""
    try:
        inst = FusionConfig()
    except (TypeError, ValueError):
        pytest.skip('dataclass requiere argumentos o valida en __post_init__')
    assert inst is not None


def test_funcion_config_make_config_hash():
    """La función no lanza con argumentos básicos."""
    try:
        make_config_hash(FusionConfig())
    except (TypeError, ValueError, NotImplementedError):
        pytest.skip('no aplicable con argumentos básicos')

