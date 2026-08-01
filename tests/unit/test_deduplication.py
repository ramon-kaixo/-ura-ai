"""Tests para motor/core/web/cleaner/deduplication.py — Fase 4 (B2)."""

from __future__ import annotations

import threading
from typing import Any

from motor.core.web.cleaner.deduplication import DeduplicationEngine


class FakeStats:
    def __init__(self) -> None:
        self.documents_removed_duplicate_hash = 0
        self.documents_removed_duplicate_url = 0
        self.documents_unique = 0


def _doc(url: str, text: str, quality: float, metadata: dict | None = None) -> Any:
    return type(
        "WebDocument",
        (),
        {"url": url, "text": text, "quality_score": quality, "metadata": metadata or {}},
    )()


class TestDeduplicationEngine:
    def test_no_duplicates_keeps_all(self) -> None:
        docs = [_doc("http://a.com/1", "uno", 0.5), _doc("http://a.com/2", "dos", 0.6)]
        result = DeduplicationEngine().deduplicate(docs)
        assert len(result) == 2
        assert result == docs

    def test_same_url_keeps_higher_quality(self) -> None:
        low = _doc("http://a.com/x", "contenido", 0.3)
        high = _doc("http://a.com/x", "contenido", 0.9)
        result = DeduplicationEngine().deduplicate([low, high])
        assert result == [high]

    def test_url_duplicate_normalized(self) -> None:
        first = _doc("http://a.com/x", "contenido", 0.5)
        variant = _doc("HTTP://A.com/x?utm=1", "contenido", 0.5)
        result = DeduplicationEngine().deduplicate([first, variant])
        assert len(result) == 1

    def test_duplicate_by_content_hash(self) -> None:
        a = _doc("http://a.com/1", "mismo texto", 0.4)
        b = _doc("http://a.com/2", "mismo texto", 0.4)
        result = DeduplicationEngine().deduplicate([a, b])
        assert result == [a]

    def test_duplicate_by_canonical_url(self) -> None:
        a = _doc("http://a.com/art", "texto a", 0.4, {"canonical_url": "http://a.com/canon"})
        b = _doc("http://b.com/art", "texto b", 0.4, {"canonical_url": "http://a.com/canon"})
        result = DeduplicationEngine().deduplicate([a, b])
        assert len(result) == 1

    def test_replacement_removes_previous_from_all_indexes(self) -> None:
        low = _doc("http://a.com/1", "bajo", 0.2)
        high = _doc("http://a.com/2", "bajo", 0.9)
        stats = FakeStats()
        result = DeduplicationEngine().deduplicate([low, high], stats)
        assert result == [high]
        assert stats.documents_removed_duplicate_hash == 1

    def test_stats_url_counter(self) -> None:
        stats = FakeStats()
        DeduplicationEngine().deduplicate(
            [_doc("http://a.com/x", "t1", 0.5), _doc("http://a.com/x", "t2", 0.5)],
            stats,
        )
        assert stats.documents_removed_duplicate_url == 1

    def test_stats_documents_unique(self) -> None:
        stats = FakeStats()
        DeduplicationEngine().deduplicate(
            [
                _doc("http://a.com/1", "t1", 0.5),
                _doc("http://a.com/2", "t1", 0.5),
                _doc("http://a.com/3", "t3", 0.5),
            ],
            stats,
        )
        assert stats.documents_unique == 2

    def test_empty_input(self) -> None:
        assert DeduplicationEngine().deduplicate([]) == []

    def test_thread_safety_smoke(self) -> None:
        engine = DeduplicationEngine()
        docs = [_doc(f"http://a.com/{i}", f"texto {i}", 0.5) for i in range(20)]
        errors: list[Exception] = []

        def worker() -> None:
            try:
                engine.deduplicate(docs)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
