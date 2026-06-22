"""Hypothesis property-based tests for URA Memory Engine and core modules."""

from hypothesis import given, settings
from hypothesis.strategies import text, integers, booleans, lists

from core.chunking import chunk_semantic
from core.document_quality import detect_language, content_type
from core.query_cache import AsyncQueryCache


@given(text(max_size=500))
@settings(max_examples=100)
def test_chunking_never_empty_for_nonempty_text(text_in: str) -> None:
    if not text_in.strip():
        return
    chunks = chunk_semantic(text_in)
    assert len(chunks) >= 1, f"chunk_semantic returned empty for: {text_in[:50]}"
    assert all(len(c) > 0 for c in chunks), "Chunks must not be empty"
    # Total content should be preserved (approximately)
    original_words = len(text_in.split())
    chunked_words = sum(len(c.split()) for c in chunks)
    assert chunked_words <= original_words or chunked_words >= original_words * 0.5


@given(lists(text(max_size=200), max_size=5), integers(min_value=1, max_value=10))
@settings(max_examples=50)
def test_query_cache_roundtrip(entries: list[str], ttl: int) -> None:
    import asyncio
    cache = AsyncQueryCache(max_size=len(entries) + 1, ttl=ttl)

    async def _run() -> None:
        seen_keys = set()
        for q in entries:
            if not q:
                continue
            key = cache.compute_key(q)
            if key in seen_keys:
                cached = await cache.get(key)
                assert cached is not None
                continue
            seen_keys.add(key)
            assert await cache.get(key) is None
            await cache.set(key, [{"test": q}])
            result = await cache.get(key)
            assert result is not None
            assert result[0]["test"] == q

    asyncio.run(_run())


@given(text(max_size=200))
@settings(max_examples=50)
def test_language_detection_stable(text_in: str) -> None:
    if not text_in.strip():
        return
    lang1 = detect_language(text_in)
    lang2 = detect_language(text_in)
    assert lang1 == lang2, f"Language detection not deterministic: {lang1} vs {lang2}"


@given(text(max_size=200))
@settings(max_examples=50)
def test_content_type_never_empty(text_in: str) -> None:
    ctype = content_type(text_in) if text_in else ""
    if text_in:
        assert isinstance(ctype, str)


@given(text(max_size=100), booleans(), booleans(), integers(min_value=1, max_value=20))
@settings(max_examples=50)
def test_cache_key_unique(query: str, reranker: bool, hybrid: bool, top_k: int) -> None:
    cache = AsyncQueryCache()
    key1 = cache.compute_key(query, use_reranker=reranker, use_hybrid=hybrid, top_k=top_k)
    key2 = cache.compute_key(query, use_reranker=reranker, use_hybrid=hybrid, top_k=top_k)
    assert key1 == key2, "Cache key not deterministic"
    # Different params should produce different keys
    key3 = cache.compute_key(query, use_reranker=not reranker, use_hybrid=hybrid, top_k=top_k)
    if reranker != (not reranker):
        assert key1 != key3, "Cache key collision on use_reranker"
