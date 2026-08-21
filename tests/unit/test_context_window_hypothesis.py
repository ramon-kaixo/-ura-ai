"""Tests property-based (Hypothesis) para motor/assistant/context_window.

Deterministas en CI vía derandomize=True.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from motor.assistant.context_window import ContextWindow
from motor.assistant.models import Message

st_texto = st.text(alphabet="abc ", max_size=60)
st_mensajes = st.lists(
    st.tuples(st.sampled_from(["user", "assistant"]), st_texto),
    min_size=0,
    max_size=20,
)


def _a_messages(pares: list[tuple[str, str]]) -> list[Message]:
    return [Message(role=r, content=c) for r, c in pares]


@settings(derandomize=True, max_examples=50)
@given(pares=st_mensajes, presupuesto=st.integers(min_value=8, max_value=512))
def test_trim_nunca_aumenta_y_cabe_en_presupuesto(
    pares: list[tuple[str, str]], presupuesto: int
) -> None:
    msgs = _a_messages(pares)
    ventana = ContextWindow(max_tokens=presupuesto + 1024, reserve_tokens=1024)
    recortados = ventana.trim_to_budget(msgs, max_tokens=presupuesto)
    assert len(recortados) <= len(msgs)
    total = sum(m.token_estimate() for m in recortados)
    assert total <= presupuesto


@settings(derandomize=True, max_examples=50)
@given(pares=st_mensajes, sistema=st_texto)
def test_build_context_prefiere_los_ultimos(
    pares: list[tuple[str, str]], sistema: str
) -> None:
    msgs = _a_messages(pares)
    ventana = ContextWindow()
    elegidos = ventana.build_context(msgs, system_prompt=sistema)
    if pares and elegidos:
        assert elegidos[-1].content == msgs[-1].content
