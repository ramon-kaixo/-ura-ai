"""Tests de citas y trazabilidad (F24-B8)."""

from __future__ import annotations

import threading
import time

from motor.core.web.citation.citation import (
    CitationBundle,
    CitationEngine,
    CitationRecord,
    Evidence,
    make_evidence_id,
)
from motor.core.web.cleaner.url_utils import content_hash, get_document_id
from motor.core.web.models import WebDocument
from motor.core.web.summarizer.summarizer import ExtractiveSummarizer


def _doc(
    text: str = "This is a test document. It has multiple sentences. For testing citation engine.",
    url: str = "http://example.com/page",
    title: str = "Test Title",
    quality: float = 1.0,
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


# ── make_evidence_id ────────────────────────


class TestMakeEvidenceId:
    def test_consistent(self) -> None:
        e1 = make_evidence_id("doc1", 0, "abc123")
        e2 = make_evidence_id("doc1", 0, "abc123")
        assert e1 == e2
        assert len(e1) == 16

    def test_different_position(self) -> None:
        assert make_evidence_id("doc1", 0, "abc") != make_evidence_id("doc1", 1, "abc")

    def test_different_document(self) -> None:
        assert make_evidence_id("doc1", 0, "abc") != make_evidence_id("doc2", 0, "abc")


# ── Evidence ────────────────────────────────


class TestEvidence:
    def test_create(self) -> None:
        e = Evidence(
            evidence_id="abc123",
            document_url="http://example.com/page",
            canonical_url=None,
            title="Test",
            document_index=0,
            sentence_position=2,
            fragment="This is a sentence.",
            content_hash="hash123",
            document_id="doc1",
            fetched_at=time.time(),
            quality_score=0.9,
        )
        assert e.evidence_id == "abc123"

    def test_to_dict(self) -> None:
        e = Evidence(
            evidence_id="abc123",
            document_url="http://example.com/page",
            canonical_url="http://canon.com/page",
            title="Test",
            document_index=0,
            sentence_position=2,
            fragment="This is a sentence.",
            content_hash="hash123",
            document_id="doc1",
            fetched_at=1000.0,
            quality_score=0.9,
        )
        d = e.to_dict()
        assert d["evidence_id"] == "abc123"
        assert d["canonical_url"] == "http://canon.com/page"


# ── CitationRecord ──────────────────────────


class TestCitationRecord:
    def test_create(self) -> None:
        c = CitationRecord(
            evidence_id="abc123",
            document_url="http://example.com/page",
            title="Test",
            fragment="A sentence.",
            citation_index=0,
            document_index=0,
        )
        assert c.evidence_id == "abc123"


# ── CitationBundle ─────────────────────────


class TestCitationBundle:
    def test_create(self) -> None:
        bundle = CitationBundle(
            summary="A summary.",
            citations=[],
            evidence=[],
            traceability_report={"total_citations": 0},
        )
        assert bundle.summary == "A summary."

    def test_to_dict(self) -> None:
        bundle = CitationBundle(
            summary="Summary text.",
            citations=[
                CitationRecord(
                    evidence_id="e1",
                    document_url="http://a.com",
                    title="A",
                    fragment="Frag.",
                    citation_index=0,
                    document_index=0,
                ),
            ],
            evidence=[],
        )
        d = bundle.to_dict()
        assert d["summary"] == "Summary text."
        assert len(d["citations"]) == 1


# ── CitationEngine ──────────────────────────


def _summarize(text: str, max_len: int = 5) -> tuple:
    """Helper: crea un resumen a partir de un texto."""
    doc = _doc(text=text)
    s = ExtractiveSummarizer()
    summary = s.summarize([doc], max_length=max_len)
    return summary, [doc]


class TestCitationEngine:
    def test_single_document_single_citation(self) -> None:
        summary, docs = _summarize("This is the first sentence. This is the second sentence.")
        bundle = CitationEngine().build(summary, docs)
        assert bundle.traceability_report["total_citations"] > 0
        assert bundle.traceability_report["unique_documents"] == 1
        assert all(c.evidence_id for c in bundle.citations)

    def test_multiple_citations_same_document(self) -> None:
        summary, docs = _summarize(
            "First sentence here. Second sentence here. Third sentence here. Fourth sentence here. Fifth sentence here.",
        )
        bundle = CitationEngine().build(summary, docs)
        assert bundle.traceability_report["total_citations"] >= 2
        # Todas las citas deben ser del mismo documento
        assert len({c.document_url for c in bundle.citations}) == 1

    def test_multi_document(self) -> None:
        d1 = _doc(
            text="Alpha first sentence. Alpha second sentence.",
            url="http://a.com",
            title="Doc A",
        )
        d2 = _doc(
            text="Beta first sentence. Beta second sentence.",
            url="http://b.com",
            title="Doc B",
        )
        s = ExtractiveSummarizer()
        summary = s.summarize([d1, d2], max_length=4)
        bundle = CitationEngine().build(summary, [d1, d2])
        assert bundle.traceability_report["unique_documents"] == 2
        urls_in_citations = {c.document_url for c in bundle.citations}
        assert "http://a.com" in urls_in_citations
        assert "http://b.com" in urls_in_citations

    def test_content_hash_integrity(self) -> None:
        summary, docs = _summarize("Unique sentence one. Unique sentence two.")
        bundle = CitationEngine().build(summary, docs)
        doc_hash = content_hash(docs[0].text or "")
        for e in bundle.evidence:
            assert e.content_hash == doc_hash

    def test_document_id_integrity(self) -> None:
        summary, docs = _summarize("One sentence here. Two sentences here.")
        bundle = CitationEngine().build(summary, docs)
        expected_id = get_document_id("http://example.com/page")
        for e in bundle.evidence:
            assert e.document_id == expected_id

    def test_citation_ordering(self) -> None:
        """Las citas deben aparecer en el mismo orden que en el resumen."""
        d1 = _doc(
            text="This is document A. It has great content. For testing purposes.",
            url="http://a.com",
        )
        d2 = _doc(
            text="This is document B. It also has content. For testing citations.",
            url="http://b.com",
        )
        s = ExtractiveSummarizer()
        summary = s.summarize([d1, d2], max_length=6)
        bundle = CitationEngine().build(summary, [d1, d2])
        for i, c in enumerate(bundle.citations):
            assert c.citation_index == i

    def test_evidence_deduplication(self) -> None:
        """Dos citas de la misma evidencia comparten evidence_id."""
        summary, docs = _summarize("Only sentence. Another sentence.")
        bundle = CitationEngine().build(summary, docs)
        # Cada evidencia es única (diferente sentence_position)
        if len(bundle.citations) >= 2:
            assert len(bundle.evidence) <= len(bundle.citations)

    def test_canonical_url_in_evidence(self) -> None:
        doc = _doc(
            text="Sentence one here. Sentence two here.",
            url="http://example.com/page",
            canonical="http://canon.com/page",
        )
        s = ExtractiveSummarizer()
        summary = s.summarize([doc], max_length=2)
        bundle = CitationEngine().build(summary, [doc])
        for e in bundle.evidence:
            assert e.canonical_url == "http://canon.com/page"

    def test_traceability_report_has_counts(self) -> None:
        summary, docs = _summarize("First. Second. Third.")
        bundle = CitationEngine().build(summary, docs)
        r = bundle.traceability_report
        assert "total_citations" in r
        assert "unique_documents" in r
        assert "evidence_count" in r
        assert "citations_per_document" in r

    def test_empty_document(self) -> None:
        doc = _doc(text="")
        s = ExtractiveSummarizer()
        summary = s.summarize([doc])
        bundle = CitationEngine().build(summary, [doc])
        assert bundle.traceability_report["total_citations"] == 0

    def test_thread_safe(self) -> None:
        doc = _doc(text="Thread safety test. Should not crash. Citation test.")
        s = ExtractiveSummarizer()
        summary = s.summarize([doc])
        engine = CitationEngine()
        errors = []

        def run() -> None:
            try:
                engine.build(summary, [doc])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ── Pipeline integration ─────────────────────


class TestPipelineCitation:
    def test_cite_via_pipeline(self) -> None:
        from motor.core.web.pipeline import WebPipeline
        from motor.core.web.registry import Registry

        pipeline = WebPipeline(Registry())
        doc = _doc(text="Citation pipeline test. For verifying integration.")
        s = ExtractiveSummarizer()
        summary = s.summarize([doc])
        bundle = pipeline.cite(summary, [doc])
        assert isinstance(bundle, CitationBundle)
        assert bundle.traceability_report["unique_documents"] == 1
