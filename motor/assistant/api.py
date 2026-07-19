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
    "conversacion": {
        "es": (
            "Eres URA, un asistente conversacional inteligente. "
            "Responde de forma natural y directa, sin extenderte. "
            "Sé conciso pero completo. Habla en español."
        ),
        "en": (
            "You are URA, an intelligent conversational assistant. "
            "Respond naturally and directly, don't overexplain. "
            "Be concise but complete. Speak in English."
        ),
    },
    "trabajo": {
        "es": (
            "Eres URA, un asistente profesional. "
            "Responde de forma precisa y estructurada. "
            "Usa bullet points cuando sea apropiado. Ve al grano."
        ),
        "en": (
            "You are URA, a professional assistant. "
            "Respond precisely and structured. "
            "Use bullet points when appropriate. Get to the point."
        ),
    },
    "explicacion": {
        "es": (
            "Eres URA, un tutor experto. "
            "Explica paso a paso con ejemplos concretos. "
            "Profundiza en causas, mecanismos y consecuencias."
        ),
        "en": (
            "You are URA, an expert tutor. "
            "Explain step by step with concrete examples. "
            "Go deep into causes, mechanisms and consequences."
        ),
    },
}


def _build_system_prompt(mode_value: str, analysis: dict, lang_code: str) -> str:
    mode_prompts = _SYSTEM_PROMPTS.get(mode_value, _SYSTEM_PROMPTS["conversacion"])
    system_prompt = mode_prompts.get(lang_code, mode_prompts["es"])

    if analysis.get("sentiment_action"):
        if lang_code == "en":
            system_prompt += f" The user seems {analysis['sentiment']}. {analysis['sentiment_action']}."
        else:
            system_prompt += f" El usuario parece {analysis['sentiment']}. {analysis['sentiment_action']}."
    if analysis.get("interruption_context"):
        system_prompt += f" [Context: {analysis['interruption_context']}]"
    if analysis.get("episodic_context"):
        system_prompt += f" [Previous conversations: {analysis['episodic_context']}]"
    return system_prompt


_FALLBACK_REPLIES = {
    "es": "Lo siento, no puedo conectar con la IA ahora. ¿Pruebo de nuevo o preguntas otra cosa?",
    "en": "Sorry, I can't reach the AI model now. Try again or ask something else?",
}


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
    lang_code = analysis.get("language", "es")

    engine.add_message(cid, "user", resolved)

    system_prompt = _build_system_prompt(mode.value, analysis, lang_code)

    return intent, mode, resolved, system_prompt, conv, lang_code


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse | StreamingResponse:
    client_ip = http_request.client.host if http_request.client else "unknown"
    _rate_limiter.check(client_ip)

    engine = get_engine()
    llm = get_llm()
    cid = request.conversation_id or ""

    intent, mode, resolved, system_prompt, conv, lang_code = _process(engine, llm, cid, request.message, request.mode)

    if request.stream:
        async def event_stream():
            try:
                if hasattr(llm, 'generate_async'):
                    reply = await llm.generate_async(
                        cid, resolved, mode,
                        intent_value=intent.value,
                        system_prompt=system_prompt,
                    )
                else:
                    reply = llm.generate(cid, resolved, mode, intent_value=intent.value, system_prompt=system_prompt)
            except Exception:
                reply = _FALLBACK_REPLIES.get(lang_code, _FALLBACK_REPLIES["es"])

            engine.add_message(cid, "assistant", reply)
            event = StreamEvent("complete", {
                "reply": reply,
                "conversation_id": cid,
                "intent": intent.value,
                "mode": mode.value,
            })
            yield event.to_sse()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    try:
        reply = llm.generate(
            cid, resolved, mode,
            intent_value=intent.value,
            system_prompt=system_prompt,
        )
    except Exception:
        reply = _FALLBACK_REPLIES.get(lang_code, _FALLBACK_REPLIES["es"])

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
