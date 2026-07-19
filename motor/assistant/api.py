"""FastAPI endpoint for the conversational assistant."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from motor.assistant.conversation import ConversationEngine
from motor.assistant.models import ConversationMode

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: str = ""
    message: str
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


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
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

    reply = f"[{conv.state.mode.value.upper()}] Recibido: {request.message}"
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
