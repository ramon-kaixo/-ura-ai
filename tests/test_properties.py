"""Hypothesis property-based tests for URA core modules."""

from hypothesis import given, settings
from hypothesis.strategies import booleans, integers, text

from core.chunking import chunk_semantic
from core.document_quality import detect_language
from core.query_cache import AsyncQueryCache


@given(text(max_size=500))
@settings(max_examples=50)
def test_chunking_invariants(text_in: str) -> None:
    if not text_in.strip():
        return
    chunks = chunk_semantic(text_in)
    assert len(chunks) >= 1
    assert all(len(c) > 0 for c in chunks)


@given(text(max_size=200), booleans(), booleans(), integers(min_value=1, max_value=10))
@settings(max_examples=30)
def test_cache_key_properties(query: str, r: bool, h: bool, k: int) -> None:
    cache = AsyncQueryCache()
    key = cache.compute_key(query, use_reranker=r, use_hybrid=h, top_k=k)
    assert len(key) == 64
    key2 = cache.compute_key(query, use_reranker=r, use_hybrid=h, top_k=k)
    assert key == key2  # determinista


@given(text(max_size=300))
@settings(max_examples=30)
def test_language_stable(text_in: str) -> None:
    if not text_in.strip():
        return
    lang1 = detect_language(text_in)
    lang2 = detect_language(text_in)
    assert lang1 == lang2
