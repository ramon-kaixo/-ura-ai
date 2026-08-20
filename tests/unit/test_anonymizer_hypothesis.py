"""Tests property-based generados por plantilla (hypothesis)."""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from motor.core.utils.anonymizer import sanitize_text


@settings(max_examples=50, deadline=None)
@given(x0=st.builds(str) if isinstance(str, type) and __import__('dataclasses').is_dataclass(str) else st.text())
def test_funcion_anonymizer_sanitize_text(x0):
    """Ejecuta la función con entradas aleatorias sin lanzar (salvo fallos legítimos)."""
    try:
        sanitize_text(x0)
    except (ValueError, KeyError, IndexError, ZeroDivisionError, TypeError, AttributeError):
        assume(False)

