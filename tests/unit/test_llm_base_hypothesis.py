"""Tests property-based (Hypothesis) para motor/core/llm/base.py.

Deterministas en CI vía derandomize=True.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from motor.core.llm.base import validate_provider


class _NoEsProvider:
    pass


@settings(derandomize=True, max_examples=30)
@given(atributo=st.text(alphabet="abcdefghij", min_size=1, max_size=8))
def test_validate_provider_rechaza_no_providers(atributo: str) -> None:
    class _Rara:
        pass

    setattr(_Rara, atributo, 1)
    resultado = validate_provider(_Rara)
    assert not resultado.valid or resultado.errors


@settings(derandomize=True, max_examples=20)
@given(nombre=st.text(min_size=0, max_size=5))
def test_validate_provider_nunca_explota(nombre: str) -> None:
    type(f"Dinamica_{nombre or 'x'}_{abs(hash(nombre))}", (_NoEsProvider,), {})
    resultado = validate_provider(_NoEsProvider)
    assert hasattr(resultado, "errors")
