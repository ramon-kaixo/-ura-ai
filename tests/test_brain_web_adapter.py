"""Tests for WebLearningAdapter (motor/brain/web_adapter.py)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from motor.brain.web_adapter import WebLearningAdapter


@pytest.fixture
def adapter() -> WebLearningAdapter:
    a = WebLearningAdapter()
    a._crawler = MagicMock()
    a._searcher = MagicMock()
    a._summarizer = MagicMock()
    return a


class TestSearch:
    def test_search_returns_list(self, adapter: WebLearningAdapter) -> None:
        searcher_instance = MagicMock()
        searcher_instance.search.return_value = [
            {"url": "http://example.com", "title": "Test", "snippet": "snippet"}
        ]
        adapter._searcher.return_value = searcher_instance
        results = adapter.search("test query")
        assert isinstance(results, list)
        assert len(results) == 1

    def test_search_scores_relevance(self, adapter: WebLearningAdapter) -> None:
        searcher_instance = MagicMock()
        searcher_instance.search.return_value = [
            {"url": "http://ex.com", "title": "test result", "snippet": "about test"}
        ]
        adapter._searcher.return_value = searcher_instance
        results = adapter.search("test query")
        assert results[0]["relevance"] > 0

    def test_search_no_searcher(self) -> None:
        a = WebLearningAdapter()
        with patch.object(a, "_load_modules"):
            a._searcher = None
            results = a.search("test")
            assert results == [{"error": "No searcher available"}]


class TestCrawl:
    def test_crawl_returns_dict(self, adapter: WebLearningAdapter) -> None:
        crawler_instance = MagicMock()
        crawler_instance.crawl.return_value.content = "page content"
        adapter._crawler.return_value = crawler_instance
        result = adapter.crawl("http://example.com")
        assert result["status"] == "ok"
        assert "page content" in result["content"]

    def test_crawl_no_crawler(self) -> None:
        a = WebLearningAdapter()
        with patch.object(a, "_load_modules"):
            a._crawler = None
            result = a.crawl("http://ex.com")
            assert result == {"error": "No crawler available"}

    def test_crawl_error(self, adapter: WebLearningAdapter) -> None:
        crawler_instance = MagicMock()
        crawler_instance.crawl.side_effect = Exception("timeout")
        adapter._crawler.return_value = crawler_instance
        result = adapter.crawl("http://ex.com")
        assert result["status"] == "error"


class TestSummarize:
    def test_summarize_returns_string(self, adapter: WebLearningAdapter) -> None:
        summarizer_instance = MagicMock()
        summarizer_instance.summarize.return_value = "summary text"
        adapter._summarizer.return_value = summarizer_instance
        result = adapter.summarize("long text to summarize")
        assert result == "summary text"

    def test_summarize_no_summarizer(self) -> None:
        a = WebLearningAdapter()
        with patch.object(a, "_load_modules"):
            a._summarizer = None
            result = a.summarize("text")
            assert result == "No summarizer available"


class TestLearnFromWeb:
    def test_learn_from_web_returns_dict(self, adapter: WebLearningAdapter) -> None:
        searcher_instance = MagicMock()
        searcher_instance.search.return_value = [
            {"url": "http://ex.com", "title": "Result", "snippet": "content about X"}
        ]
        adapter._searcher.return_value = searcher_instance
        adapter._crawler.return_value.crawl.return_value.content = "page content here " * 50
        adapter._summarizer.return_value.summarize.return_value = "summary"

        result = adapter.learn_from_web("test topic")
        assert result["query"] == "test topic"
        assert result["sources_found"] >= 1


class TestScore:
    def test_score_exact_match(self, adapter: WebLearningAdapter) -> None:
        score = adapter._score("test query", {"title": "test", "snippet": "this is a query result"})
        assert score == 1.0

    def test_score_no_match(self, adapter: WebLearningAdapter) -> None:
        score = adapter._score("test query", {"title": "unrelated", "snippet": "nothing here"})
        assert score == 0.0

    def test_score_partial(self, adapter: WebLearningAdapter) -> None:
        score = adapter._score("test query", {"title": "test only", "snippet": "no match here"})
        assert 0.0 < score <= 1.0

    def test_score_empty_query(self, adapter: WebLearningAdapter) -> None:
        score = adapter._score("", {"title": "anything", "snippet": "something"})
        assert score == 0.0
