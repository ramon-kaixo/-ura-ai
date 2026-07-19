"""Tests del ExtractiveSummarizer (F24-B7)."""

from __future__ import annotations

import threading

from motor.core.web.models import WebDocument
from motor.core.web.summarizer.summarizer import (
    ExtractiveSummarizer,
    SentenceInfo,
    Summary,
    split_sentences,
)


def _doc(
    text: str = "This is a test document. It has multiple sentences. For testing purposes only.",
    url: str = "http://example.com/page",
    title: str = "Test Title",
    quality: float = 1.0,
) -> WebDocument:
    return WebDocument(url=url, title=title, text=text, quality_score=quality)


# ── split_sentences ─────────────────────────


class TestSplitSentences:
    def test_simple(self) -> None:
        result = split_sentences("Hello world. This is a test.")
        assert len(result) == 2
        assert result[0] == "Hello world."
        assert result[1] == "This is a test."

    def test_single_sentence(self) -> None:
        result = split_sentences("Just one sentence.")
        assert result == ["Just one sentence."]

    def test_empty(self) -> None:
        result = split_sentences("")
        assert result == [""]

    def test_exclamation_and_question(self) -> None:
        result = split_sentences("Stop! Are you sure? Let's go.")
        assert len(result) == 3

    def test_abbreviation_splits(self) -> None:
        result = split_sentences("Dr. Smith is here. He came late.")
        # "Dr." se considera frase por tener >= 2 caracteres
        assert len(result) == 3

    def test_newlines_normalized(self) -> None:
        result = split_sentences("First line.\nSecond line.\n\nThird.")
        assert len(result) == 3


# ── SentenceInfo ────────────────────────────


class TestSentenceInfo:
    def test_create(self) -> None:
        s = SentenceInfo(text="Hello.", score=0.5, position=0, document_url="http://a.com", document_title="A")
        assert s.text == "Hello."
        assert s.score == 0.5


# ── Summary ─────────────────────────────────


class TestSummary:
    def test_create(self) -> None:
        s = Summary(
            text="Hello world.",
            sentences=["Hello world."],
            source_documents=["http://a.com"],
            sentence_origins=[{"url": "http://a.com", "title": "A", "position": 0, "score": 0.5}],
            compression_ratio=0.5,
        )
        assert s.text == "Hello world."
        assert len(s.sentences) == 1


# ── ExtractiveSummarizer ────────────────────


class TestExtractiveSummarizer:
    def test_single_document(self) -> None:
        doc = _doc(text="Python is a programming language. It is widely used. Many developers prefer it.")
        summarizer = ExtractiveSummarizer()
        result = summarizer.summarize([doc], max_length=2)
        assert isinstance(result, Summary)
        assert 1 <= len(result.sentences) <= 2
        assert result.source_documents == ["http://example.com/page"]

    def test_multi_document(self) -> None:
        d1 = _doc(text="First document sentence one. First document sentence two.", url="http://a.com")
        d2 = _doc(text="Second document sentence one. Second document sentence two.", url="http://b.com")
        result = ExtractiveSummarizer().summarize([d1, d2], max_length=4)
        assert len(result.sentences) == 4
        assert len(result.source_documents) == 2

    def test_empty_document(self) -> None:
        doc = _doc(text="")
        result = ExtractiveSummarizer().summarize([doc])
        assert result.text == ""
        assert result.sentences == []

    def test_empty_document_list(self) -> None:
        result = ExtractiveSummarizer().summarize([], max_length=5)
        assert result.sentences == []
        assert result.text == ""

    def test_short_document(self) -> None:
        doc = _doc(text="Short.")
        result = ExtractiveSummarizer().summarize([doc], max_length=5)
        assert len(result.sentences) <= 1

    def test_max_length(self) -> None:
        doc = _doc(
            text="One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten."
            " Eleven. Twelve. Thirteen. Fourteen. Fifteen.",
        )
        result = ExtractiveSummarizer().summarize([doc], max_length=3)
        assert len(result.sentences) <= 3

    def test_redundancy_removed(self) -> None:
        doc = _doc(text="Hello world. Hello world. Unique sentence here.")
        result = ExtractiveSummarizer().summarize([doc], max_length=5)
        texts = [s.lower() for s in result.sentences]
        assert texts.count("hello world.") == 0 or texts.count("hello world.") == 1

    def test_order_preserved(self) -> None:
        doc = _doc(text="Alpha. Beta. Gamma. Delta.")
        result = ExtractiveSummarizer().summarize([doc], max_length=4)
        # Even with scoring, basic ordering should be preserved within one doc
        if len(result.sentences) >= 2:
            idx_alpha = next(i for i, s in enumerate(result.sentences) if "Alpha" in s)
            idx_beta = next(i for i, s in enumerate(result.sentences) if "Beta" in s)
            assert idx_alpha < idx_beta

    def test_trazability(self) -> None:
        d1 = _doc(text="Alpha sentence here. Beta sentence here.", url="http://a.com")
        result = ExtractiveSummarizer().summarize([d1], max_length=5)
        for origin in result.sentence_origins:
            assert origin["url"] == "http://a.com"
            assert "position" in origin
            assert "score" in origin

    def test_multi_document_trazability(self) -> None:
        d1 = _doc(text="Doc A first sentence. Doc A second sentence.", url="http://a.com")
        d2 = _doc(text="Doc B first sentence. Doc B second sentence.", url="http://b.com")
        result = ExtractiveSummarizer().summarize([d1, d2], max_length=4)
        urls_in_origins = {o["url"] for o in result.sentence_origins}
        assert "http://a.com" in urls_in_origins
        assert "http://b.com" in urls_in_origins

    def test_compression_ratio(self) -> None:
        doc = _doc(
            text="First sentence here with many words for testing purposes. "
            "Second sentence also has content for testing compression. "
            "Third sentence here with some more words for the test. "
            "Fourth sentence here with additional content for testing. "
            "Fifth and final sentence with enough words for the test.",
        )
        result = ExtractiveSummarizer().summarize([doc], max_length=2)
        assert 0.0 <= result.compression_ratio < 1.0

    def test_no_text_modification(self) -> None:
        doc = _doc(text="This sentence is unique. Another different sentence for testing.")
        result = ExtractiveSummarizer().summarize([doc], max_length=5)
        for s in result.sentences:
            # Each sentence must appear verbatim in the original text
            assert s in doc.text

    def test_thread_safe(self) -> None:
        doc = _doc(text="Thread safety test. Multiple calls. Should not crash.")
        summarizer = ExtractiveSummarizer()
        errors = []

        def run() -> None:
            try:
                summarizer.summarize([doc])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_title_influence(self) -> None:
        doc = _doc(
            title="Python Programming",
            text="Java is a language. Python is great. Ruby is fun.",
        )
        result = ExtractiveSummarizer().summarize([doc], max_length=1)
        # The sentence with "Python" should score higher due to title overlap
        assert "Python" in result.text

    def test_all_sentences_when_max_large(self) -> None:
        doc = _doc(text="One. Two. Three. Four. Five.")
        result = ExtractiveSummarizer().summarize([doc], max_length=100)
        assert len(result.sentences) == 5


# ── Pipeline integration ─────────────────────


class TestPipelineSummarizer:
    def test_summarize_documents_via_pipeline(self) -> None:
        from motor.core.web.pipeline import WebPipeline
        from motor.core.web.registry import Registry

        pipeline = WebPipeline(Registry())
        doc = _doc(text="First sentence here. Second sentence here. Third sentence here.")
        result = pipeline.summarize_documents([doc], max_length=2)
        assert isinstance(result, Summary)
        assert 1 <= len(result.sentences) <= 2
        assert result.compression_ratio >= 0.0
