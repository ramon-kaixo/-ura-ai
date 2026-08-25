"""E2E tests for assistant chat flow. Requires Ollama for chat test."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from motor.assistant.main import app
from motor.core.secrets import get_secret

HAS_OLLAMA = False
try:
    r = httpx.get("http://localhost:11434/api/tags", timeout=2)
    HAS_OLLAMA = r.status_code == 200
except Exception:  # noqa: S110
    pass


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200


def test_metrics_endpoint(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "ura_requests_total" in r.text


@pytest.mark.skipif(not HAS_OLLAMA, reason="Ollama not running")
@pytest.mark.timeout(15)
def test_chat_basic(client: TestClient) -> None:
    # Auth requerida cuando URA_API_KEY está definida (AuthMiddleware)
    headers: dict[str, Any] = {}
    api_key = get_secret("URA_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    r = client.post("/api/v1/chat", json={"message": "hola", "mode": "conversacion"}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
