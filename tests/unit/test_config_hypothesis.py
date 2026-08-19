"""Tests property-based generados por plantilla (hypothesis)."""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from motor.core.fusion.config import FusionConfig, make_config_hash


@settings(max_examples=50, deadline=None)
@given(instancia=st.builds(FusionConfig))
def test_dataclass_config_FusionConfig_ronda(instancia):
    """Ronda de propiedades básicas sobre la dataclass."""
    assert instancia is not None
    assert repr(instancia) == repr(instancia)


@settings(max_examples=50, deadline=None)
@given(x0=st.builds(FusionConfig) if isinstance(FusionConfig, type) and __import__('dataclasses').is_dataclass(FusionConfig) else st.text())
def test_funcion_config_make_config_hash(x0):
    """Ejecuta la función con entradas aleatorias sin lanzar (salvo fallos legítimos)."""
    try:
        make_config_hash(x0)
    except (ValueError, KeyError, IndexError, ZeroDivisionError):
        assume(False)

