"""Tests de limpieza y deduplicación (F24-B5)."""

from __future__ import annotations

import hashlib
import threading

from motor.core.web.cleaner.cleaner import CleanedResult, CleanedStats, DocumentCleaner
from motor.core.web.cleaner.deduplication import DeduplicationEngine
from motor.core.web.cleaner.url_utils import content_hash, get_document_id, normalize_url
from motor.core.web.models import WebDocument


def _doc(
    text: str = "some valid content here",
    url: str = "http://example.com/page",
    quality: float = 1.0,
    title: str = "title",
    canonical: str | None = None,
) -> WebDocument:
    meta = {}
    if canonical:
        meta["canonical_url"] = canonical
    return WebDocument(
        url=url,
        title=title,
        text=text,
        quality_score=quality,
        metadata=meta,  # type: ignore[arg-type]
    )


# ── content_hash ──────────────────────────────


class TestContentHash:
    def test_consistent(self) -> None:
        h1 = content_hash("hello world")
        h2 = content_hash("hello world")
        assert h1 == h2
        assert len(h1) == 64

    def test_different(self) -> None:
        assert content_hash("hello") != content_hash("world")

    def test_whitespace_insensitive(self) -> None:
        assert content_hash("hello   world") == content_hash("hello world")

    def test_empty(self) -> None:
        assert content_hash("") == hashlib.sha256(b"").hexdigest()


# ── normalize_url ─────────────────────────────


class TestNormalizeUrl:
    def test_fragment_removed(self) -> None:
        assert normalize_url("http://example.com/page#section") == "http://example.com/page"

    def test_scheme_lowercase(self) -> None:
        assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"

    def test_host_lowercase(self) -> None:
        assert normalize_url("http://EXAMPLE.com/Page") == "http://example.com/Page"

    def test_trailing_slash_removed(self) -> None:
        assert normalize_url("http://example.com/path/") == "http://example.com/path"

    def test_root_slash_kept(self) -> None:
        assert normalize_url("http://example.com/") == "http://example.com/"

    def test_no_path(self) -> None:
        assert normalize_url("http://example.com") == "http://example.com/"

    def test_query_preserved(self) -> None:
        assert (
            normalize_url("http://example.com/page?a=1&b=2")
            == "http://example.com/page?a=1&b=2"
        )

    def test_fragment_removed_with_query(self) -> None:
        assert (
            normalize_url("http://example.com/page?a=1#section")
            == "http://example.com/page?a=1"
        )


# ── get_document_id ──────────────────────────


class TestDocumentId:
    def test_from_url(self) -> None:
        assert get_document_id("http://Example.com/Page") == "http://example.com/Page"

    def test_from_canonical(self) -> None:
        assert (
            get_document_id("http://example.com/other", canonical_url="http://canonical.com/page")
            == "http://canonical.com/page"
        )

    def test_canonical_takes_precedence(self) -> None:
        assert (
            get_document_id("http://example.com/a", canonical_url="http://example.com/b")
            == "http://example.com/b"
        )

    def test_url_normalized(self) -> None:
        assert get_document_id("HTTPS://EXAMPLE.COM/Path/") == "https://example.com/Path"


# ── DocumentCleaner ──────────────────────────


class TestDocumentCleaner:
    def test_removes_empty(self) -> None:
        docs = [_doc(text=""), _doc(text="three words here")]
        result = DocumentCleaner().clean(docs)
        assert len(result.documents) == 1
        assert result.documents[0].text == "three words here"

    def test_removes_below_min_words(self) -> None:
        docs = [_doc(text="hi"), _doc(text="three words here")]
        result = DocumentCleaner(min_words=3).clean(docs)
        assert len(result.documents) == 1

    def test_normalizes_urls(self) -> None:
        docs = [_doc(url="HTTPS://Example.COM/Path/")]
        result = DocumentCleaner().clean(docs)
        assert result.documents[0].url == "https://example.com/Path"

    def test_preserves_valid_docs(self) -> None:
        docs = [_doc(text="good content here", url="http://a.com"), _doc(text="more content here", url="http://b.com")]
        result = DocumentCleaner().clean(docs)
        assert len(result.documents) == 2

    def test_stats_received(self) -> None:
        docs = [_doc(text="a"), _doc(text="b")]
        result = DocumentCleaner().clean(docs)
        assert result.stats.documents_received == 2

    def test_stats_removed_empty(self) -> None:
        docs = [_doc(text=""), _doc(text="three valid words")]
        result = DocumentCleaner().clean(docs)
        assert result.stats.documents_removed_empty == 1

    def test_empty_input(self) -> None:
        result = DocumentCleaner().clean([])
        assert len(result.documents) == 0
        assert result.stats.documents_received == 0


# ── DeduplicationEngine ──────────────────────


class TestDedupEngine:
    def test_exact_url(self) -> None:
        docs = [_doc(text="a", url="http://example.com/page"), _doc(text="b", url="http://example.com/page")]
        result = DeduplicationEngine().deduplicate(docs)
        assert len(result) == 1

    def test_url_normalized_match(self) -> None:
        docs = [_doc(text="a", url="http://example.com/page"), _doc(text="b", url="HTTP://EXAMPLE.COM/page")]
        result = DeduplicationEngine().deduplicate(docs)
        assert len(result) == 1

    def test_canonical_url(self) -> None:
        docs = [
            _doc(text="a", url="http://example.com/a", canonical="http://canon.com/x"),
            _doc(text="b", url="http://example.com/b", canonical="http://canon.com/x"),
        ]
        result = DeduplicationEngine().deduplicate(docs)
        assert len(result) == 1

    def test_content_hash(self) -> None:
        docs = [_doc(text="same content", url="http://a.com"), _doc(text="same content", url="http://b.com")]
        result = DeduplicationEngine().deduplicate(docs)
        assert len(result) == 1

    def test_keeps_highest_quality(self) -> None:
        docs = [
            _doc(text="same", url="http://a.com", quality=0.5),
            _doc(text="same", url="http://b.com", quality=0.9),
        ]
        result = DeduplicationEngine().deduplicate(docs)
        assert len(result) == 1
        assert result[0].quality_score == 0.9

    def test_keeps_highest_quality_url_dup(self) -> None:
        docs = [
            _doc(text="a", url="http://example.com/page", quality=0.3),
            _doc(text="b", url="http://example.com/page", quality=0.8),
        ]
        result = DeduplicationEngine().deduplicate(docs)
        assert len(result) == 1
        assert result[0].quality_score == 0.8

    def test_keeps_highest_quality_canonical(self) -> None:
        docs = [
            _doc(text="a", url="http://a.com/x", quality=0.4, canonical="http://canon.com/y"),
            _doc(text="b", url="http://b.com/x", quality=0.7, canonical="http://canon.com/y"),
        ]
        result = DeduplicationEngine().deduplicate(docs)
        assert len(result) == 1
        assert result[0].quality_score == 0.7

    def test_no_duplicates(self) -> None:
        docs = [
            _doc(text="alpha", url="http://a.com", quality=0.5),
            _doc(text="beta", url="http://b.com", quality=0.6),
            _doc(text="gamma", url="http://c.com", quality=0.7),
        ]
        result = DeduplicationEngine().deduplicate(docs)
        assert len(result) == 3

    def test_empty_list(self) -> None:
        result = DeduplicationEngine().deduplicate([])
        assert result == []

    def test_stats_url(self) -> None:
        stats = CleanedStats(documents_received=2)
        docs = [_doc(text="a", url="http://example.com/page"), _doc(text="b", url="http://example.com/page")]
        DeduplicationEngine().deduplicate(docs, stats=stats)
        assert stats.documents_removed_duplicate_url > 0
        assert stats.documents_unique == 1

    def test_stats_hash(self) -> None:
        stats = CleanedStats(documents_received=2)
        docs = [_doc(text="same", url="http://a.com"), _doc(text="same", url="http://b.com")]
        DeduplicationEngine().deduplicate(docs, stats=stats)
        assert stats.documents_removed_duplicate_hash == 1

    def test_thread_safe(self) -> None:
        engine = DeduplicationEngine()
        docs = [_doc(text="a", url=f"http://example.com/{i}") for i in range(100)]
        errors = []

        def run() -> None:
            try:
                engine.deduplicate(docs)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ── CleanedStats ──────────────────────────────


class TestCleanedStats:
    def test_duplication_pct(self) -> None:
        stats = CleanedStats(documents_received=10)
        stats.documents_removed_empty = 2
        stats.documents_removed_duplicate_url = 1
        assert stats.documents_removed == 3
        assert stats.duplication_pct == 30.0

    def test_zero_division(self) -> None:
        stats = CleanedStats()
        assert stats.duplication_pct == 0.0

    def test_to_dict(self) -> None:
        stats = CleanedStats(documents_received=5, documents_unique=3)
        d = stats.to_dict()
        assert d["documents_received"] == 5
        assert d["documents_unique"] == 3


# ── Pipeline integration ─────────────────────


class TestPipelineClean:
    def test_clean_via_pipeline(self) -> None:
        from motor.core.web.pipeline import WebPipeline
        from motor.core.web.registry import Registry

        pipeline = WebPipeline(Registry())
        docs = [
            _doc(text="alpha version here", url="http://example.com/a", quality=0.5),
            _doc(text="beta version here", url="http://example.com/a", quality=0.9),
            _doc(text=""),
        ]
        result = pipeline.clean(docs)
        assert isinstance(result, CleanedResult)
        assert len(result.documents) == 1
        assert result.stats.documents_removed_empty == 1
        assert result.stats.documents_unique == 1
        assert result.documents[0].quality_score == 0.9
