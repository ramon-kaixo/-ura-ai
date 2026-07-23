"""E2E tests for assistant chat flow. Requires Ollama for chat test."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from motor.assistant.main import app

HAS_OLLAMA = False
try:
    import httpx
    r = httpx.get("http://localhost:11434/api/tags", timeout=2)
    HAS_OLLAMA = r.status_code == 200
except Exception:
    pass


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "ura_requests_total" in r.text


@pytest.mark.skipif(not HAS_OLLAMA, reason="Ollama not running")
@pytest.mark.timeout(15)
def test_chat_basic(client):
    r = client.post("/api/v1/chat", json={"message": "hola", "mode": "conversacion"})
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
