"""E2E tests for health and metrics endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from motor.assistant.main import app


class TestHealth:
    def test_health_returns_200(self):
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_has_components(self):
        client = TestClient(app)
        data = client.get("/health").json()
        assert "components" in data

    def test_health_has_status(self):
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["status"] == "ok"


class TestMetrics:
    def test_metrics_returns_200(self):
        client = TestClient(app)
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_metrics_is_prometheus_text(self):
        client = TestClient(app)
        r = client.get("/metrics")
        assert r.headers["content-type"].startswith("text/plain")

    def test_metrics_has_counters(self):
        client = TestClient(app)
        text = client.get("/metrics").text
        assert "# TYPE ura_requests_total counter" in text
