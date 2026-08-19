"""Tests property-based generados por plantilla (hypothesis)."""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from motor.core.web.models import SearchResult, SourceMetadata, WebDocument, Citation


@settings(max_examples=50, deadline=None)
@given(instancia=st.builds(SearchResult))
def test_dataclass_models_SearchResult_ronda(instancia):
    """Ronda de propiedades básicas sobre la dataclass."""
    assert instancia is not None
    assert repr(instancia) == repr(instancia)


@settings(max_examples=50, deadline=None)
@given(instancia=st.builds(SourceMetadata))
def test_dataclass_models_SourceMetadata_ronda(instancia):
    """Ronda de propiedades básicas sobre la dataclass."""
    assert instancia is not None
    assert repr(instancia) == repr(instancia)


@settings(max_examples=50, deadline=None)
@given(instancia=st.builds(WebDocument))
def test_dataclass_models_WebDocument_ronda(instancia):
    """Ronda de propiedades básicas sobre la dataclass."""
    assert instancia is not None
    assert repr(instancia) == repr(instancia)


@settings(max_examples=50, deadline=None)
@given(instancia=st.builds(Citation))
def test_dataclass_models_Citation_ronda(instancia):
    """Ronda de propiedades básicas sobre la dataclass."""
    assert instancia is not None
    assert repr(instancia) == repr(instancia)

