"""Tests para motor/core/web/config.py y motor/assistant/main.py."""
from __future__ import annotations

from unittest import mock

import pytest

from motor.core.web.config import WebConfig


class TestWebConfig:
    def test_defaults(self) -> None:
        c = WebConfig()
        assert c.default_searcher == "duckduckgo"
        assert c.default_crawler == "httpx"
        assert c.default_extractor == "readability"
        assert c.default_ranker == "default"
        assert c.default_summarizer == "llm"
        assert c.search_timeout == 10
        assert c.crawl_timeout == 30
        assert c.extract_timeout == 15
        assert c.max_results_per_source == 10
        assert c.max_documents_to_summarize == 5
        assert "URA/1.0" in c.user_agent
        assert c.robots_txt_cache_ttl == 3600
        assert c.respect_robots_txt is True

    def test_sobrescribe(self) -> None:
        c = WebConfig(
            {
                "default_searcher": "google",
                "search_timeout": "5",
                "crawl_timeout": 60,
                "respect_robots_txt": False,
                "user_agent": "custom-ua",
            }
        )
        assert c.default_searcher == "google"
        assert c.search_timeout == 5
        assert c.crawl_timeout == 60
        assert c.respect_robots_txt is False
        assert c.user_agent == "custom-ua"

    def test_timeout_str(self) -> None:
        c = WebConfig({"search_timeout": "20"})
        assert c.search_timeout == 20

    def test_none_config(self) -> None:
        c = WebConfig(None)
        assert c.default_searcher == "duckduckgo"


class TestAssistantMain:
    def test_app_estructura(self) -> None:
        from motor.assistant.main import app

        assert app.title == "URA Assistant"
        assert app.version == "1.0.0"

    def test_health_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from motor.assistant.main import app

        with mock.patch("motor.assistant.main.get_assistant_health") as gh:
            gh.return_value.snapshot.return_value = {"ok": True}
            client = TestClient(app)
            r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"

    def test_root_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from motor.assistant.main import app

        client = TestClient(app)
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["name"] == "URA Assistant"

    def test_metrics_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from motor.assistant.main import app

        with mock.patch("motor.observability.prometheus_exporter.export_metrics", return_value="# URA metrics\n"):
            client = TestClient(app)
            r = client.get("/metrics")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")
        assert "# URA metrics" in r.text

    def test_main(self, monkeypatch) -> None:
        import motor.assistant.main as m

        monkeypatch.setattr(m.config, "ensure_data_dir", mock.Mock())
        uvicorn_run = mock.Mock()
        monkeypatch.setattr("motor.assistant.main.uvicorn.run", uvicorn_run)
        m.main()
        uvicorn_run.assert_called_once()
        assert uvicorn_run.call_args.args[0] == "motor.assistant.main:app"
