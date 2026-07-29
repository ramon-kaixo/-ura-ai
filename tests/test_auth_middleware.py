"""Tests for motor/assistant/auth.py — AuthMiddleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from motor.assistant import auth


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/api/v1/chat")
    async def chat():
        return {"status": "ok"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestAuthMiddleware:
    def test_auth_disabled(self, app, client, monkeypatch):
        monkeypatch.setattr(auth.config, "api_key", "")
        app.add_middleware(auth.AuthMiddleware)
        resp = client.get("/api/v1/chat", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 200

    def test_auth_enabled_no_header(self, app, client, monkeypatch):
        monkeypatch.setattr(auth.config, "api_key", "test-key-123")
        app.add_middleware(auth.AuthMiddleware)
        resp = client.get("/api/v1/chat")
        assert resp.status_code == 401
        assert resp.json()["error"] == "Unauthorized"

    def test_auth_enabled_wrong_key(self, app, client, monkeypatch):
        monkeypatch.setattr(auth.config, "api_key", "test-key-123")
        app.add_middleware(auth.AuthMiddleware)
        resp = client.get("/api/v1/chat", headers={"Authorization": "Bearer wrong-key"})
        assert resp.status_code == 401

    def test_auth_enabled_valid_key(self, app, client, monkeypatch):
        monkeypatch.setattr(auth.config, "api_key", "test-key-123")
        app.add_middleware(auth.AuthMiddleware)
        resp = client.get("/api/v1/chat", headers={"Authorization": "Bearer test-key-123"})
        assert resp.status_code == 200

    def test_non_chat_path_skips_auth(self, app, client, monkeypatch):
        monkeypatch.setattr(auth.config, "api_key", "test-key-123")
        app.add_middleware(auth.AuthMiddleware)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_auth_no_bearer_prefix(self, app, client, monkeypatch):
        monkeypatch.setattr(auth.config, "api_key", "test-key-123")
        app.add_middleware(auth.AuthMiddleware)
        resp = client.get("/api/v1/chat", headers={"Authorization": "test-key-123"})
        assert resp.status_code == 401
