"""Tests del DocumentRanker (F24-B6)."""

from __future__ import annotations

import threading

from motor.core.web.models import WebDocument
from motor.core.web.ranker.ranker import DEFAULT_WEIGHTS, DocumentRanker, RankedDocument, RankingScore


def _doc(
    text: str = "some valid content here for testing",
    url: str = "http://example.com/page",
    quality: float = 1.0,
    title: str = "Test Title",
    word_count: int | None = None,
    canonical: str | None = None,
) -> WebDocument:
    meta = {}
    if canonical:
        meta["canonical_url"] = canonical
    wc = word_count or len(text.split())
    return WebDocument(
        url=url,
        title=title,
        text=text,
        quality_score=quality,
        word_count=wc,
        metadata=meta,  # type: ignore[arg-type]
    )


# ── RankingScore ─────────────────────────────


class TestRankingScore:
    def test_total(self) -> None:
        s = RankingScore(quality=3.0, position=2.0, length=0.5)
        assert s.total == 5.5

    def test_total_with_penalties(self) -> None:
        s = RankingScore(quality=3.0, short_penalty=-2.0, empty_penalty=-5.0)
        assert s.total == -4.0

    def test_to_dict(self) -> None:
        s = RankingScore(quality=2.5, position=1.0)
        d = s.to_dict()
        assert d["quality"] == 2.5
        assert d["position"] == 1.0
        assert "total" in d

    def test_default_zero(self) -> None:
        s = RankingScore()
        assert s.total == 0.0


# ── RankedDocument ──────────────────────────


class TestRankedDocument:
    def test_final_score(self) -> None:
        doc = _doc()
        s = RankingScore(quality=3.0)
        rd = RankedDocument(document=doc, score=s)
        assert rd.final_score == 3.0

    def test_score_breakdown(self) -> None:
        doc = _doc()
        s = RankingScore(quality=2.0, position=1.5)
        rd = RankedDocument(document=doc, score=s)
        b = rd.score_breakdown
        assert b["quality"] == 2.0
        assert b["position"] == 1.5


# ── DocumentRanker ──────────────────────────


class TestDocumentRanker:
    def test_basic_ordering(self) -> None:
        docs = [
            _doc(text="low quality content here", quality=0.3),
            _doc(text="high quality content here", quality=0.9, url="http://example.com/high"),
        ]
        ranker = DocumentRanker()
        result = ranker.rank("test", docs)
        assert len(result) == 2
        assert result[0].document.quality_score == 0.9
        assert result[1].document.quality_score == 0.3

    def test_tie_breaker_url(self) -> None:
        docs = [
            _doc(url="http://example.com/banana"),
            _doc(url="http://example.com/apple"),
        ]
        ranker = DocumentRanker(weights={"quality": 0.0, "position": 0.0, "length": 0.0})
        result = ranker.rank("test", docs)
        assert result[0].document.url == "http://example.com/apple"
        assert result[1].document.url == "http://example.com/banana"

    def test_configurable_weights(self) -> None:
        docs = [
            _doc(text="python programming guide here for test", quality=0.5, url="http://a.com"),
            _doc(text="unrelated content here for testing only", quality=0.9, url="http://b.com"),
        ]
        ranker = DocumentRanker(weights={"quality": 10.0, "title_match": 0.0, "text_match": 0.0})
        result = ranker.rank("python", docs)
        # quality dominates, so b (0.9) should rank higher
        assert result[0].document.url == "http://b.com"

    def test_title_match_boosts(self) -> None:
        docs = [
            _doc(title="python tutorial for beginners", text="unrelated content here for testing"),
            _doc(title="unrelated title here for testing", text="some other content for testing"),
        ]
        ranker = DocumentRanker()
        result = ranker.rank("python", docs)
        assert result[0].document.title == "python tutorial for beginners"

    def test_url_match_boosts(self) -> None:
        docs = [
            _doc(url="http://example.com/python-tutorial"),
            _doc(url="http://example.com/other-page"),
        ]
        ranker = DocumentRanker()
        result = ranker.rank("python", docs)
        assert "python" in result[0].document.url

    def test_position_influence(self) -> None:
        docs = [
            _doc(text="some good content here for testing", url="http://a.com"),
            _doc(text="other good content here for testing", url="http://b.com"),
        ]
        ranker = DocumentRanker()
        # first doc at position 5, second at position 0
        positions = {"http://a.com": 5, "http://b.com": 0}
        result = ranker.rank("test", docs, positions=positions)
        assert result[0].document.url == "http://b.com"

    def test_long_content_gets_higher_length_score(self) -> None:
        long = "word " * 500
        short = "short text here"
        docs = [
            _doc(text=long, word_count=500, url="http://a.com"),
            _doc(text=short, word_count=3, url="http://b.com"),
        ]
        ranker = DocumentRanker(weights={
            "quality": 0.0, "position": 0.0, "title_match": 0.0,
            "text_match": 0.0, "url_match": 0.0, "canonical_bonus": 0.0,
        })
        result = ranker.rank("test", docs)
        assert result[0].document.url == "http://a.com"

    def test_canonical_bonus(self) -> None:
        docs = [
            _doc(url="http://example.com/a", canonical="http://canon.com/x"),
            _doc(url="http://example.com/b"),
        ]
        ranker = DocumentRanker(weights={
            "quality": 0.0, "position": 0.0, "length": 0.0,
            "title_match": 0.0, "text_match": 0.0, "url_match": 0.0,
        })
        result = ranker.rank("test", docs)
        assert result[0].document.url == "http://example.com/a"

    def test_short_penalty(self) -> None:
        docs = [
            _doc(word_count=3, text="short", url="http://a.com"),
            _doc(word_count=100, text="adequate content here for testing", url="http://b.com"),
        ]
        ranker = DocumentRanker(weights={
            "quality": 0.0, "position": 0.0, "length": 0.0,
            "title_match": 0.0, "text_match": 0.0, "url_match": 0.0,
            "canonical_bonus": 0.0,
        })
        result = ranker.rank("test", docs)
        assert result[0].document.url == "http://b.com"

    def test_empty_penalty(self) -> None:
        docs = [
            _doc(word_count=0, text="", url="http://a.com"),
            _doc(word_count=50, text="some content here for testing", url="http://b.com"),
        ]
        ranker = DocumentRanker(weights={
            "quality": 0.0, "position": 0.0, "length": 0.0,
            "title_match": 0.0, "text_match": 0.0, "url_match": 0.0,
            "canonical_bonus": 0.0,
        })
        result = ranker.rank("test", docs)
        assert result[0].document.url == "http://b.com"

    def test_score_breakdown_present(self) -> None:
        docs = [_doc(text="python content here for testing")]
        result = DocumentRanker().rank("python", docs)
        rd = result[0]
        assert isinstance(rd.score_breakdown, dict)
        assert "total" in rd.score_breakdown
        assert rd.final_score == rd.score_breakdown["total"]

    def test_empty_document_list(self) -> None:
        result = DocumentRanker().rank("test", [])
        assert result == []

    def test_empty_query(self) -> None:
        docs = [_doc(), _doc(url="http://example.com/other")]
        result = DocumentRanker().rank("", docs)
        assert len(result) == 2

    def test_thread_safe(self) -> None:
        ranker = DocumentRanker()
        docs = [_doc(text=f"document number {i}", url=f"http://example.com/{i}") for i in range(50)]
        errors = []

        def run() -> None:
            try:
                ranker.rank("test", docs)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_default_weights_unchanged(self) -> None:
        ranker = DocumentRanker()
        w = ranker.weights
        for k, v in DEFAULT_WEIGHTS.items():
            assert w[k] == v, f"{k}: expected {v}, got {w[k]}"

    def test_custom_weights_merge(self) -> None:
        ranker = DocumentRanker(weights={"quality": 5.0})
        assert ranker.weights["quality"] == 5.0
        assert ranker.weights["position"] == DEFAULT_WEIGHTS["position"]


# ── Pipeline integration ─────────────────────


class TestPipelineRanker:
    def test_rank_documents_via_pipeline(self) -> None:
        from motor.core.web.pipeline import WebPipeline
        from motor.core.web.registry import Registry

        pipeline = WebPipeline(Registry())
        docs = [
            _doc(text="quality python content here for testing", quality=0.9, url="http://a.com"),
            _doc(text="low quality python content for testing", quality=0.3, url="http://b.com"),
        ]
        result = pipeline.rank_documents("python", docs)
        assert len(result) == 2
        assert isinstance(result[0], RankedDocument)
        assert result[0].document.quality_score == 0.9
        assert "total" in result[0].score_breakdown
