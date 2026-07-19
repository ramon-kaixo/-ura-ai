"""Test end-to-end determinista del pipeline Web Intelligence (F24-B9).

Ejecuta toda la cadena sin acceso a Internet usando dobles de prueba:
search → crawl → extract → clean → dedup → rank → summarize → cite

Este test es la referencia para F25: cualquier regresión en la integración
entre etapas se detectará inmediatamente.
"""

from __future__ import annotations

from motor.core.web.citation.citation import CitationBundle, CitationEngine
from motor.core.web.cleaner.cleaner import DocumentCleaner
from motor.core.web.cleaner.deduplication import DeduplicationEngine
from motor.core.web.extractor.providers.html_extractor import HtmlExtractor
from motor.core.web.ranker.ranker import DocumentRanker
from motor.core.web.summarizer.summarizer import ExtractiveSummarizer, Summary

# ── Datos de prueba ─────────────────────────

HTML_PYTHON = """<html><head>
<title>Python Guide</title>
<meta name="description" content="Complete Python programming guide">
<meta name="author" content="Python Docs">
<meta name="language" content="en">
</head><body>
<p>Python is a high-level programming language. It was created by Guido van Rossum.
Python emphasizes code readability. It is widely used in web development.
Many developers prefer Python for data science and machine learning.
Python has a large standard library. The language supports multiple paradigms.</p>
<script>unused</script>
<style>.hidden{}</style>
</body></html>"""

HTML_JAVA = """<html><head>
<title>Java Programming</title>
<meta name="description" content="Java programming language overview">
<meta name="author" content="Java Docs">
</head><body>
<p>Java is a class-based programming language. It is designed for portability.
Java runs on billions of devices worldwide. The language is used for enterprise applications.
Android development uses Java extensively. Java has strong typing and garbage collection.</p>
</body></html>"""

HTML_EMPTY = """<html><head><title>Empty Page</title></head><body></body></html>"""

HTML_DUPLICATE = """<html><head>
<title>Python Guide</title>
<meta name="description" content="Complete Python programming guide">
</head><body>
<p>Python is a high-level programming language. It was created by Guido van Rossum.
Python emphasizes code readability. It is widely used in web development.
Many developers prefer Python for data science and machine learning.
Python has a large standard library. The language supports multiple paradigms.</p>
</body></html>"""

HTML_ERROR = "<html><head><title>Error</title></head><body><p>Not found</p></body></html>"

URLS = {
    "http://example.com/python": HTML_PYTHON,
    "http://example.com/java": HTML_JAVA,
    "http://example.com/empty": HTML_EMPTY,
    "http://example.com/python-dup": HTML_DUPLICATE,
    "http://example.com/error": HTML_ERROR,
}

QUERY = "python programming"
MAX_SUMMARY_SENTENCES = 6


class TestPipelineE2E:
    """Test end-to-end determinista del pipeline completo."""

    def _extract_all(self) -> list:
        extractor = HtmlExtractor()
        docs = []
        for url, html in URLS.items():
            doc = extractor.extract(html, url)
            docs.append(doc)
        return docs

    def test_full_pipeline(self) -> None:
        # 1. Extract
        docs = self._extract_all()
        assert len(docs) == 5
        assert docs[0].title == "Python Guide"
        assert len(docs[2].text.split()) < 3  # empty page → minimal text

        # 2. Clean
        cleaner = DocumentCleaner()
        cleaned = cleaner.clean(docs)
        assert cleaned.stats.documents_removed_empty >= 1  # empty page removed
        assert len(cleaned.documents) < 5

        # 3. Deduplicate
        dedup = DeduplicationEngine()
        unique = dedup.deduplicate(cleaned.documents, stats=cleaned.stats)
        assert len(unique) < len(cleaned.documents)  # python-dup removed

        # 4. Rank
        ranker = DocumentRanker()
        ranked = ranker.rank(QUERY, unique)
        assert len(ranked) == len(unique)
        # Python document should rank higher for "python" query
        if len(ranked) >= 2:
            assert "python" in ranked[0].document.url.lower()
            assert ranked[0].final_score >= 0

        # 5. Summarize
        summarizer = ExtractiveSummarizer()
        # Use unique docs (after dedup) for summarization
        summary = summarizer.summarize(unique, max_length=MAX_SUMMARY_SENTENCES)
        assert isinstance(summary, Summary)
        assert len(summary.sentences) > 0
        assert len(summary.sentences) <= MAX_SUMMARY_SENTENCES
        assert summary.compression_ratio >= 0.0
        # Verbatim constraint: each sentence appears in at least one source
        import re

        all_text_normalized = " ".join(re.sub(r"\s+", " ", d.text or "") for d in unique)
        for s in summary.sentences:
            normalized_s = re.sub(r"\s+", " ", s)
            assert normalized_s in all_text_normalized, f"Sentence not found in sources: {s[:50]}"

        # 6. Cite
        engine = CitationEngine()
        bundle = engine.build(summary, unique)
        assert isinstance(bundle, CitationBundle)
        assert bundle.traceability_report["total_citations"] == len(summary.sentences)
        assert bundle.traceability_report["evidence_count"] > 0
        assert bundle.traceability_report["unique_documents"] >= 1

        # Verify evidence integrity
        for e in bundle.evidence:
            assert e.fragment in all_text_normalized
            assert len(e.evidence_id) == 16

        # Verify citation integrity
        for c in bundle.citations:
            assert c.evidence_id in {e.evidence_id for e in bundle.evidence}

        # 7. Serialization
        d = bundle.to_dict()
        assert d["summary"] == bundle.summary
        assert len(d["citations"]) == len(bundle.citations)
        assert len(d["evidence"]) == len(bundle.evidence)

    def test_pipeline_via_webpipeline(self) -> None:
        """Ejecuta el pipeline via WebPipeline."""
        from motor.core.web.pipeline import WebPipeline
        from motor.core.web.registry import Registry

        pipeline = WebPipeline(Registry())

        # Simula crawl + extract manual
        extractor = HtmlExtractor()
        docs = [extractor.extract(HTML_PYTHON, "http://example.com/python")]

        cleaned = pipeline.clean(docs)
        assert len(cleaned.documents) >= 1

        ranked = pipeline.rank_documents(QUERY, cleaned.documents)
        assert len(ranked) >= 1

        summary = pipeline.summarize_documents(cleaned.documents, max_length=4)
        assert len(summary.sentences) >= 1

        bundle = pipeline.cite(summary, cleaned.documents)
        assert bundle.traceability_report["total_citations"] >= 1

    def test_empty_pipeline(self) -> None:
        """Pipeline con documentos vacíos."""
        pipeline_stages = [
            ("clean", lambda: DocumentCleaner().clean([])),
            ("dedup", lambda: DeduplicationEngine().deduplicate([])),
            ("rank", lambda: DocumentRanker().rank("test", [])),
            ("summarize", lambda: ExtractiveSummarizer().summarize([], 5)),
        ]
        for name, fn in pipeline_stages:
            result = fn()
            assert result is not None, f"{name} returned None"

    def test_determinism(self) -> None:
        """Dos ejecuciones deben producir resultados idénticos."""
        docs = self._extract_all()
        cleaner = DocumentCleaner()
        dedup = DeduplicationEngine()

        def run() -> tuple:
            c = cleaner.clean(list(docs))  # fresh copy
            u = dedup.deduplicate(c.documents)
            s = ExtractiveSummarizer().summarize(u, max_length=4)
            b = CitationEngine().build(s, u)
            return tuple(s.fragment for s in b.citations), b.traceability_report["total_citations"]

        r1 = run()
        r2 = run()
        assert r1 == r2
