"""HTTP routes for the chat API."""

from __future__ import annotations

import time
import uuid
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from motor.assistant.api.handlers import (
    _FALLBACK_REPLIES,
    _detect_tool_name,
    _enrich_prompt,
    _execute_command,
    _moderator,
    _process,
    _tool_manager,
    get_engine,
    get_llm,
)
from motor.assistant.api.middleware import _log, _rate_limiter, _scoped_cid
from motor.assistant.health import get_assistant_health
from motor.assistant.metrics import errors_total, request_latency, requests_total, tokens_total
from motor.assistant.models import UserIntent
from motor.assistant.streaming import StreamEvent
from motor.observability.tracing_platform import CorrelationId, TraceContext

_MAX_MESSAGE_LENGTH = 100000

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatRequest(BaseModel):
    user_id: str = ""
    conversation_id: str = ""
    message: str = Field(..., max_length=_MAX_MESSAGE_LENGTH)
    mode: str = "conversacion"
    stream: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    intent: str = ""
    turn_count: int = 0


class FeedbackRequest(BaseModel):
    conversation_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str = ""


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse | StreamingResponse:
    correlation_id = str(uuid.uuid4())[:8]
    client_ip = http_request.client.host if http_request.client else "unknown"
    _rate_limiter.check(client_ip)
    start_time = time.monotonic()
    trace = _registrar_request(request, correlation_id)

    engine = get_engine()
    llm = get_llm()
    get_assistant_health().set_healthy("conversation", f"active: {correlation_id}")
    cid = _scoped_cid(request.user_id, request.conversation_id or uuid.uuid4().hex[:16])

    blocked = _moderar_input(request, engine, cid, correlation_id)
    if blocked is not None:
        return blocked

    plan = await _preparar_respuesta(engine, llm, cid, request)

    if request.stream:
        return _responder_streaming(llm, engine, plan)

    reply = _generar_respuesta_sync(llm, plan, trace, correlation_id)
    output_mod = _moderator.moderate_output(reply)
    if output_mod.flagged:
        reply = output_mod.sanitized_text
    engine.add_message(cid, "assistant", reply)

    _registrar_exito(start_time, plan, correlation_id, reply)

    return ChatResponse(
        conversation_id=plan.display_cid,
        reply=reply,
        intent=plan.intent.value,
        turn_count=plan.conv.state.turn_count if plan.conv.state else 0,
    )


def _registrar_request(request: ChatRequest, correlation_id: str) -> TraceContext:
    trace = TraceContext(source="assistant_api", destination="llm", correlation_id=CorrelationId(correlation_id))
    _log.info(
        "chat request",
        extra={
            "correlation_id": correlation_id,
            "user_id": request.user_id,
            "mode": request.mode,
            "message_len": len(request.message),
        },
    )
    requests_total.inc(mode=request.mode, status="received")
    return trace


def _moderar_input(request: ChatRequest, engine: Any, cid: str, correlation_id: str) -> ChatResponse | None:
    input_mod = _moderator.moderate_input(request.message)
    if not input_mod.flagged:
        return None
    reply = "No puedo procesar esa solicitud. Por favor, haz una pregunta apropiada."
    engine.add_message(cid, "user", request.message)
    engine.add_message(cid, "assistant", reply)
    _log.warning(
        "moderated input blocked", extra={"correlation_id": correlation_id, "reason": ", ".join(input_mod.categories)}
    )
    return ChatResponse(
        conversation_id=request.conversation_id or cid,
        reply=reply,
        intent="unknown",
        turn_count=2,
    )


async def _preparar_respuesta(engine: Any, llm: Any, cid: str, request: ChatRequest) -> Any:
    result = _process(engine, llm, cid, request.message, request.mode, request.user_id)
    intent, mode, resolved, system_prompt, conv, lang_code, analysis = result
    display_cid = request.conversation_id or cid.rsplit("__", 1)[-1] if "__" in cid else cid

    enriched_prompt = await _enrich_prompt(system_prompt, analysis, engine, resolved)

    if intent == UserIntent.COMMAND:
        tool_name = _detect_tool_name(resolved)
        if tool_name and _tool_manager.needs_confirmation(tool_name, resolved):
            enriched_prompt += (
                "\n\n⚠️ Este comando requiere confirmación. Pregunta al usuario si está seguro antes de ejecutarlo."
            )
        tool_result = await _execute_command(resolved, analysis)
        if tool_result:
            engine.add_message(cid, "user", f"COMANDO REAL EJECUTADO. RESULTADO:\n{tool_result[:800]}")
            enriched_prompt += "\n\nEl resultado arriba es de un comando REAL. Responde basándote en ese resultado."

    return SimpleNamespace(
        cid=cid,
        intent=intent,
        mode=mode,
        resolved=resolved,
        system_prompt=system_prompt,
        conv=conv,
        lang_code=lang_code,
        display_cid=display_cid,
        enriched_prompt=enriched_prompt,
    )


def _responder_streaming(llm: Any, engine: Any, plan: Any) -> StreamingResponse:
    async def event_stream():
        full_reply = ""
        try:
            async for token in llm.generate_stream(
                plan.cid if hasattr(plan, "cid") else "",
                plan.resolved,
                plan.mode,
                intent_value=plan.intent.value,
                system_prompt=plan.enriched_prompt,
            ):
                yield StreamEvent("token", {"text": token}).to_sse()
                full_reply = token
        except Exception as exc:
            yield StreamEvent("error", {"type": type(exc).__name__}).to_sse()
            full_reply = _FALLBACK_REPLIES.get(plan.lang_code, _FALLBACK_REPLIES["es"])

        output_mod = _moderator.moderate_output(full_reply)
        if output_mod.flagged:
            full_reply = output_mod.sanitized_text
        engine.add_message(plan.cid, "assistant", full_reply)
        yield StreamEvent(
            "complete",
            {
                "reply": full_reply,
                "conversation_id": plan.display_cid,
                "intent": plan.intent.value,
                "mode": plan.mode.value,
            },
        ).to_sse()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _generar_respuesta_sync(llm: Any, plan: Any, trace: TraceContext, correlation_id: str) -> str:
    try:
        with trace.span(message_type="llm.generate", tags={"correlation_id": correlation_id, "mode": plan.mode.value}):
            reply = llm.generate(
                plan.cid,
                plan.resolved,
                plan.mode,
                intent_value=plan.intent.value,
                system_prompt=plan.enriched_prompt,
            )
        tokens_total.inc(provider="llm", amount=len(reply.split()))
        return reply
    except Exception:
        errors_total.inc(type="llm_error", component="generation")
        return _FALLBACK_REPLIES.get(plan.lang_code, _FALLBACK_REPLIES["es"])


def _registrar_exito(start_time: float, plan: Any, correlation_id: str, reply: str) -> None:
    duration = time.monotonic() - start_time
    request_latency.observe(duration, mode=plan.mode.value)
    requests_total.inc(mode=plan.mode.value, status="success")
    _log.info(
        "chat response",
        extra={
            "correlation_id": correlation_id,
            "intent": plan.intent.value,
            "mode": plan.mode.value,
            "reply_len": len(reply),
            "duration_s": round(duration, 3),
        },
    )


@router.get("/conversations")
async def list_conversations() -> list[dict[str, Any]]:
    return get_engine().list_conversations()


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest) -> dict[str, object]:
    conv = get_engine().get_conversation(req.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    from motor.assistant.evaluation import ConversationEvaluator

    ev = ConversationEvaluator()
    ev.record_metric(req.conversation_id, "user_rating", float(req.rating), {"comment": req.comment})
    return {"status": "ok", "rating": req.rating}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, bool]:
    get_engine().delete_conversation(conversation_id)
    return {"deleted": True}


@router.get("/metrics")
async def metrics():
    from fastapi.responses import PlainTextResponse

    from motor.observability.prometheus_exporter import export_metrics

    return PlainTextResponse(content=export_metrics(), media_type="text/plain")
