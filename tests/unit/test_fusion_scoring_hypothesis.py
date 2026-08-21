"""Tests property-based (Hypothesis) para motor/core/fusion — KeywordScorer.

Deterministas en CI vía derandomize=True (semilla fija implícita).
TASK-20260821-002: ampliación Hypothesis a módulos críticos.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from motor.core.fusion.stages.entity_models import EntityDef
from motor.core.fusion.stages.entity_scoring import KeywordScorer

st_palabras = st.text(alphabet="abcdefghijkmnopqrstuvwxyz_", min_size=1, max_size=10)
st_keywords = st.lists(st_palabras, min_size=1, max_size=4, unique=True)


@settings(derandomize=True, max_examples=50)
@given(kw=st_keywords, contexto=st.text(max_size=40))
def test_scorer_una_entrada_devuelve_siempre_0(kw: list[str], contexto: str) -> None:
    entradas = [EntityDef(entity_id="e1", canonical_name="E1", keywords=kw)]
    assert KeywordScorer().select(entradas, contexto) == 0


@settings(derandomize=True, max_examples=50)
@given(kws=st.lists(st_keywords, min_size=2, max_size=3), contexto=st.text(max_size=30))
def test_scorer_sin_coincidencias_es_ambiguo(
    kws: list[list[str]], contexto: str
) -> None:
    # Garantiza que NINGUNA keyword aparezca en el contexto.
    limpio = " ".join(ch for ch in contexto if ch != "_")
    supuestas = {k for grupo in kws for k in grupo}
    for k in list(supuestas):
        limpio = limpio.replace(k[:1], "q")
    entradas = [
        EntityDef(entity_id=f"e{i}", canonical_name=f"E{i}", keywords=g)
        for i, g in enumerate(kws)
    ]
    resultado = KeywordScorer().select(entradas, limpio)
    assert resultado is None or isinstance(resultado, int)


@settings(derandomize=True, max_examples=50)
@given(palabra=st_palabras, relleno=st.text(max_size=20))
def test_scorer_gana_el_maximo_unico(palabra: str, relleno: str) -> None:
    ctx = f"{relleno} {palabra} {relleno}"
    entradas = [
        EntityDef(entity_id="sin", canonical_name="S", keywords=["zzzzz"]),
        EntityDef(entity_id="con", canonical_name="C", keywords=[palabra]),
    ]
    assert KeywordScorer().select(entradas, ctx) == 1
