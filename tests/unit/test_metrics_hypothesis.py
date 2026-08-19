"""Tests property-based para evaluation/metrics (generados por plantilla, ajustados)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from motor.core.evaluation.metrics import recall_at_k, precision_at_k, _average_precision


@settings(max_examples=50, deadline=None)
@given(
    relevant=st.sets(st.text(), min_size=1),
    retrieved=st.lists(st.text()),
    k=st.integers(min_value=0, max_value=50),
)
def test_funcion_metrics_recall_at_k(relevant, retrieved, k):
    """Recall@K con entradas válidas no lanza y devuelve [0,1]."""
    r = recall_at_k(relevant, retrieved, k)
    assert 0.0 <= r <= 1.0


@settings(max_examples=50, deadline=None)
@given(
    relevant=st.sets(st.text()),
    retrieved=st.lists(st.text()),
    k=st.integers(min_value=0, max_value=50),
)
def test_funcion_metrics_precision_at_k(relevant, retrieved, k):
    """Precision@K con entradas válidas no lanza y devuelve [0,1]."""
    r = precision_at_k(relevant, retrieved, k)
    assert 0.0 <= r <= 1.0


@settings(max_examples=50, deadline=None)
@given(relevances=st.lists(st.floats(min_value=0.0, max_value=1.0)), k=st.integers(min_value=0, max_value=50))
def test_funcion_metrics__dcg(relevances, k):
    """_dcg no lanza y devuelve float."""
    from motor.core.evaluation.metrics import _dcg

    r = _dcg(relevances, k)
    assert isinstance(r, float)
