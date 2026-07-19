"""FastAPI endpoint for the conversational assistant."""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from motor.assistant.conversation import ConversationEngine
from motor.assistant.models import ConversationMode

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

_MAX_MESSAGE_LENGTH = 100000
_RATE_LIMIT_WINDOW = 60.0
_RATE_LIMIT_MAX = 60


class ChatRequest(BaseModel):
    conversation_id: str = ""
    message: str = Field(..., max_length=_MAX_MESSAGE_LENGTH)
    mode: str = "conversacion"
    stream: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    intent: str = ""
    turn_count: int = 0


class _EngineHolder:
    engine: ConversationEngine | None = None


def get_engine() -> ConversationEngine:
    if _EngineHolder.engine is None:
        _EngineHolder.engine = ConversationEngine()
    return _EngineHolder.engine


class _RateLimiter:
    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}

    def check(self, key: str) -> None:
        now = time.monotonic()
        window_start = now - _RATE_LIMIT_WINDOW
        if key in self._requests:
            self._requests[key] = [t for t in self._requests[key] if t > window_start]
            if len(self._requests[key]) >= _RATE_LIMIT_MAX:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            self._requests[key].append(now)
        else:
            self._requests[key] = [now]


_rate_limiter = _RateLimiter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    client_ip = http_request.client.host if http_request.client else "unknown"
    _rate_limiter.check(client_ip)

    engine = get_engine()
    cid = request.conversation_id or ""
    conv = engine.get_or_create(cid)
    if request.mode:
        try:
            conv.state.mode = ConversationMode(request.mode)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}") from None

    intent = engine.detect_intent(request.message)
    resolved = engine.resolve_reference(request.message, conv.conversation_id)
    engine.add_message(conv.conversation_id, "user", resolved)

    reply = f"[{conv.state.mode.value.upper()}] Recibido: {request.message[:200]}"
    if intent.value == "greeting":
        reply = "¡Hola! ¿En qué puedo ayudarte?"
    elif intent.value == "farewell":
        reply = "¡Hasta luego! Cuídate."

    engine.add_message(conv.conversation_id, "assistant", reply)

    return ChatResponse(
        conversation_id=conv.conversation_id,
        reply=reply,
        intent=intent.value,
        turn_count=conv.state.turn_count if conv.state else 0,
    )


@router.get("/conversations")
async def list_conversations() -> list[dict[str, Any]]:
    return get_engine().list_conversations()


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, bool]:
    ok = get_engine().delete_conversation(conversation_id)
    return {"deleted": ok}
