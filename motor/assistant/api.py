"""FastAPI endpoint for the conversational assistant.
Conectado a LLM real via motor/core/llm/router.py"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from motor.assistant.conversation import ConversationEngine
from motor.assistant.llm_bridge import LLMBridge
from motor.assistant.models import ConversationMode
from motor.assistant.streaming import StreamEvent
from motor.assistant.style import StyleEngine
from motor.assistant.web_search import WebSearchIntegration

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
    style: StyleEngine | None = None
    web: WebSearchIntegration | None = None


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


def get_style() -> StyleEngine:
    if _EngineHolder.style is None:
        _EngineHolder.style = StyleEngine()
    return _EngineHolder.style


def get_web_search() -> WebSearchIntegration:
    if _EngineHolder.web is None:
        _EngineHolder.web = WebSearchIntegration()
    return _EngineHolder.web


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


def _process(engine: ConversationEngine, llm: LLMBridge, cid: str, message: str, mode_str: str) -> tuple:
    conv = engine.get_or_create(cid)
    if mode_str:
        try:
            conv.state.mode = ConversationMode(mode_str)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode_str}") from None

    analysis = engine.process_user_message(cid, message)
    intent = analysis["intent"]
    mode = analysis["mode"]
    resolved = analysis["resolved_message"]

    engine.add_message(cid, "user", resolved)

    style = get_style()
    system_prompt = style.build_system_prompt(mode, intent)

    if analysis.get("sentiment_action"):
        system_prompt += f" El usuario parece {analysis['sentiment']}. {analysis['sentiment_action']}."
    if analysis.get("interruption_context"):
        system_prompt += f" Contexto de interrupción: {analysis['interruption_context']}"
    if analysis.get("episodic_context"):
        system_prompt += f" Contexto de conversaciones anteriores: {analysis['episodic_context']}"

    if analysis.get("needs_web_search"):
        web = get_web_search()
        web_result = web.search_if_needed(message, intent.value)
        if web_result.get("results"):
            system_prompt += f"\nInformación actualizada de la web: {web_result['results']}"

    return intent, mode, resolved, system_prompt, conv


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse | StreamingResponse:
    client_ip = http_request.client.host if http_request.client else "unknown"
    _rate_limiter.check(client_ip)

    engine = get_engine()
    llm = get_llm()
    cid = request.conversation_id or ""

    intent, mode, resolved, system_prompt, conv = _process(engine, llm, cid, request.message, request.mode)

    if request.stream:
        async def event_stream():
            if hasattr(llm, 'generate_async'):
                reply = await llm.generate_async(
                    cid, resolved, mode,
                    intent_value=intent.value,
                    system_prompt=system_prompt,
                )
            else:
                reply = llm.generate(cid, resolved, mode, intent_value=intent.value, system_prompt=system_prompt)

            engine.add_message(cid, "assistant", reply)
            event = StreamEvent("complete", {
                "reply": reply,
                "conversation_id": cid,
                "intent": intent.value,
                "mode": mode.value,
            })
            yield event.to_sse()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

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
