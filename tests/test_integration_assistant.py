"""Tests de integración para el asistente conversacional (endpoint real)."""
from __future__ import annotations

import json

import httpx
import pytest

BASE_URL = "http://localhost:8003"


pytestmark = pytest.mark.skipif(
    True,
    reason="Requiere servidor GX10 en http://localhost:8003",
)


class TestAssistantAPI:
    def test_health(self):
        resp = httpx.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_chat_greeting(self):
        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat",
            json={"message": "hola", "conversation_id": "int_test1"},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "conversation_id" in data
        assert "reply" in data
        assert len(data["reply"]) > 0

    def test_chat_with_user_id(self):
        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat",
            json={"message": "hola", "user_id": "test_user", "conversation_id": "int_test2"},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data

    def test_chat_with_mode(self):
        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat",
            json={"message": "explícame qué es un repo git", "mode": "explicacion", "conversation_id": "int_test3"},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data

    def test_streaming(self):
        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat",
            json={"message": "hola", "stream": True, "conversation_id": "int_test4"},
            timeout=30,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_list_conversations(self):
        resp = httpx.get(f"{BASE_URL}/api/v1/chat/conversations", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_invalid_mode(self):
        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat",
            json={"message": "hola", "mode": "invalido"},
            timeout=5,
        )
        assert resp.status_code == 400

    def test_auth_required_when_configured(self):
        # Si no hay API key configurada, esto debe funcionar sin auth
        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat",
            json={"message": "hola"},
            timeout=10,
        )
        assert resp.status_code in (200, 401)
