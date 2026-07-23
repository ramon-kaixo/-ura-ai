"""E2E tests for assistant chat flow."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from motor.assistant.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "components" in data


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "ura_requests_total" in r.text
    assert "ura_tokens_total" in r.text


@pytest.mark.timeout(15)
def test_chat_basic(client):
    r = client.post("/api/v1/chat", json={"message": "hola", "mode": "conversacion"})
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
    assert "conversation_id" in data
