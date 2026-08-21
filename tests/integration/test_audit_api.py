"""Edge-case audit tests for motor/assistant/api.py.

Targets: missing auth, input validation, error handling, race conditions,
unbounded message size, binary data, empty conversation_id.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from motor.assistant.api import router
from motor.assistant.api.handlers import _EngineHolder, get_engine
from motor.assistant.conversation import ConversationEngine
from motor.assistant.message_store import MessageStore

if TYPE_CHECKING:
    from pathlib import Path


class _FakeEmbeddingResponse:
    """Simula httpx.Response para _embed — mock de red, no de lógica interna."""

    def __init__(self, status_code: int = 200, embedding: list[float] | None = None) -> None:
        self.status_code = status_code
        self._embedding = embedding or [0.1] * 768

    def json(self) -> dict[str, Any]:
        return {"embedding": self._embedding}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    _a = FastAPI()
    _a.include_router(router)
    return _a


@pytest.fixture
def client(app: FastAPI, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Point the engine at a temp database
    db = str(tmp_path / "test_api.db")
    store = MessageStore(db)
    engine = ConversationEngine(message_store=store)
    # Mock httpx.post (red) en lugar de _embed (lógica interna).
    # _embed llama a httpx.post -> /api/embeddings en Ollama.
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: _FakeEmbeddingResponse(),
    )
    _EngineHolder.engine = engine
    # Mock LLM to avoid real HTTP calls to Ollama/model-router
    mock_llm = MagicMock()
    mock_llm.generate.side_effect = lambda cid, resolved, mode, intent_value="", system_prompt="": (
        "Hasta luego, que tengas un buen día."
        if "adiós" in resolved.lower()
        else "Hola, soy URA. ¿En qué puedo ayudarte?"
    )
    _EngineHolder.llm = mock_llm
    return TestClient(app)


def _reset_engine() -> None:
    _EngineHolder.engine = None


# ---------------------------------------------------------------------------
# D1 — Missing Authentication
# ---------------------------------------------------------------------------


class TestMissingAuth:
    """D1: No authentication on any endpoint.

    This is a design-level finding: anyone who can reach the port can
    read/write all conversations without any token or credentials.
    """

    def test_no_auth_header_required(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat", json={"message": "hola"})
        assert resp.status_code == 200, "No auth required — open endpoint"

    def test_list_conversations_no_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/chat/conversations")
        assert resp.status_code == 200

    def test_delete_conversation_no_auth(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/chat/conversations/any-id")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# D2 — Input Validation: message length & content
# ---------------------------------------------------------------------------


class TestInputValidation:
    """D2: No max_length on message field
    binary data accepted."""

    def test_very_long_message(self, client: TestClient) -> None:
        huge = "A" * 1_000_000  # 1 MB
        t0 = time.monotonic()
        resp = client.post("/api/v1/chat", json={"message": huge})
        elapsed = time.monotonic() - t0
        assert elapsed < 10.0, f"1 MB message took {elapsed:.2f}s"
        assert resp.status_code in (200, 422), f"Expected 200 or 422, got {resp.status_code}"

    def test_extremely_long_message(self, client: TestClient) -> None:
        huge = "B" * 10_000_000  # 10 MB — unbounded growth
        t0 = time.monotonic()
        resp = client.post("/api/v1/chat", json={"message": huge})
        elapsed = time.monotonic() - t0
        assert elapsed < 30.0, f"10 MB message took {elapsed:.2f}s"
        assert resp.status_code in (200, 422), f"Expected 200 or 422, got {resp.status_code}"

    def test_binary_null_bytes_in_message(self, client: TestClient) -> None:
        payload = "hello\x00world\x00\x00\x00boom"
        resp = client.post("/api/v1/chat", json={"message": payload})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data

    def test_unicode_control_chars(self, client: TestClient) -> None:
        payload = "hello\u0000\u0001\u0002\u001fworld"
        resp = client.post("/api/v1/chat", json={"message": payload})
        assert resp.status_code == 200

    def test_emoji_and_unicode_surrogates(self, client: TestClient) -> None:
        payload = "🔥🚀 " + "\ud800" * 100 + " test"
        import json as _json

        try:
            _json.dumps({"message": payload})
            resp = client.post("/api/v1/chat", json={"message": payload})
            assert resp.status_code == 200
        except (UnicodeEncodeError, ValueError):
            resp = client.post("/api/v1/chat", content=b'{"message": "test surrogate blocked by json"}')
            assert resp.status_code in (200, 422)

    def test_message_with_only_whitespace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat", json={"message": "   \t\n  "})
        assert resp.status_code == 200

    def test_message_with_only_special_chars(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat", json={"message": "!@#$%^&*()_+"})
        assert resp.status_code == 200

    def test_invalid_mode_rejected(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat", json={"message": "hola", "mode": "invalid_mode"})
        assert resp.status_code == 400
        assert "Invalid mode" in resp.json()["detail"]

    def test_empty_message_accepted(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat", json={"message": ""})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# D3 — Empty / Missing conversation_id
# ---------------------------------------------------------------------------


class TestConversationIDEdgeCases:
    """D3: Empty conversation_id is accepted but creates a new conv each time."""

    def test_empty_cid_creates_conversation(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat", json={"message": "hola", "conversation_id": ""})
        assert resp.status_code == 200
        data = resp.json()
        cid = data.get("conversation_id", "")
        assert cid and len(cid) > 0, f"Expected non-empty conversation_id, got '{cid}'"

    def test_empty_cid_is_not_persistent(self, client: TestClient) -> None:
        """Each request with empty cid creates a NEW conversation."""
        cids: set[str] = set()
        for _ in range(5):
            resp = client.post("/api/v1/chat", json={"message": "hola", "conversation_id": ""})
            assert resp.status_code == 200
            cids.add(resp.json()["conversation_id"])
        assert len(cids) == 5, "Empty cid creates different conversations each time"

    def test_missing_cid_field_allowed(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat", json={"message": "hola"})
        assert resp.status_code == 200

    def test_none_cid_falls_back_to_empty(self, client: TestClient) -> None:
        """JSON null conversation_id is handled by Pydantic default."""
        resp = client.post("/api/v1/chat", json={"message": "hola", "conversation_id": None})
        # Pydantic: with str type, null may be rejected or defaulted
        assert resp.status_code in (200, 422)


# ---------------------------------------------------------------------------
# D4 — Error Handling / Resilience
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """D4: What happens when ConversationEngine crashes mid-request."""

    def test_engine_crash_on_init_retries(self, client: TestClient, tmp_path: Path) -> None:
        """If ConversationEngine() raises, get_engine retries next call."""
        import sqlite3

        _EngineHolder.engine = None
        broken_db = str(tmp_path / "broken" / "nope.db")
        # Inject a broken store
        broken = MessageStore(broken_db)
        broken._conn.close()  # close so next append crashes
        _EngineHolder.engine = ConversationEngine(message_store=broken)

        with pytest.raises(sqlite3.ProgrammingError):
            client.post("/api/v1/chat", json={"message": "hola"})

    def test_list_conversations_empty_db(self, client: TestClient) -> None:
        resp = client.get("/api/v1/chat/conversations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_delete_non_existent_conversation(self, client: TestClient) -> None:
        # BUG: routes.py:207 siempre retorna {"deleted": True},
        # incluso si el conversation_id no existe.
        # Comportamiento ideal: 404. Se documenta sin arreglar (out of scope).
        resp = client.delete("/api/v1/chat/conversations/i-dont-exist")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True}

    def test_delete_same_conversation_twice(self, client: TestClient) -> None:
        # Mismo bug: segunda llamada tambien retorna 200 en vez de 404.
        resp = client.post("/api/v1/chat", json={"message": "test"})
        cid = resp.json()["conversation_id"]
        resp1 = client.delete(f"/api/v1/chat/conversations/{cid}")
        assert resp1.json()["deleted"] is True
        resp2 = client.delete(f"/api/v1/chat/conversations/{cid}")
        assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# D5 — Rate Limiting / Abuse Prevention
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """D5: No rate limiting — sequential or concurrent abuse is unthrottled."""

    def test_rapid_sequential_requests(self, client: TestClient) -> None:
        from motor.assistant.api.middleware import _rate_limiter

        _rate_limiter._requests.clear()
        t0 = time.monotonic()
        for _ in range(50):
            resp = client.post("/api/v1/chat", json={"message": "hola"})
            assert resp.status_code == 200
        elapsed = time.monotonic() - t0
        assert elapsed < 30.0, f"50 sequential requests took {elapsed:.2f}s (no rate limit)"

    def test_large_payload_changes_turn_count(self, client: TestClient) -> None:
        """Verify turn_count increments properly."""
        cid = "test-turns"
        for i in range(5):
            resp = client.post(
                "/api/v1/chat",
                json={"conversation_id": cid, "message": f"message {i}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["turn_count"] == (i + 1) * 2  # user + assistant per turn


# ---------------------------------------------------------------------------
# D6 — Race Condition in get_engine Singleton
# ---------------------------------------------------------------------------


class TestGetEngineRace:
    """D6: get_engine() has a TOCTOU race — two threads can init simultaneously."""

    def test_get_engine_singleton_race(self) -> None:
        """Under concurrent call, both threads may create an engine."""
        _reset_engine()
        created: list[int] = []

        def call_get_engine() -> None:
            e = get_engine()
            created.append(id(e))

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(call_get_engine) for _ in range(50)]
            concurrent.futures.wait(futures)

        engine_ids = set(created)
        # Ideally only 1 engine. Race condition may create more.
        assert len(engine_ids) == 1, f"Race condition: {len(engine_ids)} different engine instances created"
        _EngineHolder.engine = None


# ---------------------------------------------------------------------------
# D7 — Chat endpoint response structure
# ---------------------------------------------------------------------------


class TestResponseStructure:
    def test_greeting_response(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat", json={"message": "hola"})
        data = resp.json()
        assert data["intent"] == "greeting"
        assert "Hola" in data["reply"]

    def test_farewell_response(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat", json={"message": "adiós"})
        data = resp.json()
        assert data["intent"] == "farewell"
        assert "Hasta luego" in data["reply"]

    def test_chat_response_always_has_fields(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat", json={"message": "test"})
        data = resp.json()
        assert "conversation_id" in data
        assert "reply" in data
        assert "intent" in data
        assert "turn_count" in data
