"""FastAPI endpoint for the conversational assistant.
Conectado a LLM real via motor/core/llm/router.py"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from motor.assistant.conversation import ConversationEngine
from motor.assistant.llm_bridge import LLMBridge
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
    llm: LLMBridge | None = None


def get_engine() -> ConversationEngine:
    if _EngineHolder.engine is None:
        _EngineHolder.engine = ConversationEngine()
    return _EngineHolder.engine


def get_llm() -> LLMBridge:
    if _EngineHolder.llm is None:
        try:
            from motor.core.llm.router import ModelRouter
            router = ModelRouter()
            _EngineHolder.llm = LLMBridge(get_engine(), router=router)
        except Exception:
            _EngineHolder.llm = LLMBridge(get_engine())
    return _EngineHolder.llm


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


_SYSTEM_PROMPTS = {
    "conversacion": (
        "Eres URA, un asistente conversacional inteligente. "
        "Responde de forma natural y directa, sin extenderte. "
        "Sé conciso pero completo. Lenguaje natural como entre amigos."
    ),
    "trabajo": (
        "Eres URA, un asistente profesional. "
        "Responde de forma precisa y estructurada. "
        "Usa bullet points cuando sea apropiado. Ve al grano."
    ),
    "explicacion": (
        "Eres URA, un tutor experto. "
        "Explica paso a paso con ejemplos concretos. "
        "Profundiza en causas, mecanismos y consecuencias. "
        "Asume que el usuario quiere entender realmente."
    ),
}


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    client_ip = http_request.client.host if http_request.client else "unknown"
    _rate_limiter.check(client_ip)

    engine = get_engine()
    llm = get_llm()

    cid = request.conversation_id or ""
    conv = engine.get_or_create(cid)
    if request.mode:
        try:
            conv.state.mode = ConversationMode(request.mode)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}") from None

    analysis = engine.process_user_message(cid, request.message)
    intent = analysis["intent"]
    mode = analysis["mode"]
    resolved = analysis["resolved_message"]

    engine.add_message(cid, "user", resolved)

    system_prompt = _SYSTEM_PROMPTS.get(mode.value, _SYSTEM_PROMPTS["conversacion"])

    if analysis.get("sentiment_action"):
        system_prompt += f" El usuario parece {analysis['sentiment']}. {analysis['sentiment_action']}."
    if analysis.get("interruption_context"):
        system_prompt += f" Contexto de interrupción: {analysis['interruption_context']}"
    if analysis.get("episodic_context"):
        system_prompt += f" Contexto de conversaciones anteriores: {analysis['episodic_context']}"

    reply = llm.generate(
        cid, resolved, mode,
        intent_value=intent.value,
        system_prompt=system_prompt,
    )

    engine.add_message(cid, "assistant", reply)

    return ChatResponse(
        conversation_id=cid,
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
