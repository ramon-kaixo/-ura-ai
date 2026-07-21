import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from core.mochila.guardian_opencode import OpenCodeGuardian
from core.mochila.helpers import _procesar_usage
from core.mochila.models import ChatRequest
from core.mochila.router import NoProviderAvailable
from core.mochila.streaming import _stream_from_provider
from core.mochila.tools import TOOL_SCHEMAS, ejecutar_tool


def _rechazar_si_bloqueado(provider_name: str, circuit_breaker, rate_limiter) -> None:
    if not circuit_breaker.puede_pasar(provider_name):
        h = circuit_breaker.estado(provider_name)
        raise HTTPException(
            status_code=503,
            detail={"error": f"Circuit breaker OPEN para {provider_name}", "state": h["state"]},
        )
    puede, actual, limite = rate_limiter.puede_pasar(provider_name)
    if not puede:
        raise HTTPException(
            status_code=429,
            detail={"error": f"Rate limit excedido para {provider_name}", "current": actual, "limit": limite},
        )


async def _chat_no_stream(provider, modelo, mensajes, herramientas, max_tokens, temperature) -> dict | None:
    try:
        async for chunk in provider.chat(
            modelo=modelo,
            mensajes=mensajes,
            stream=False,
            tools=herramientas,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            return chunk
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"provider: {e}")  # noqa: B904
    return None


def create_chat_router(state) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/chat/completions")
    async def v1_chat_completions(body: ChatRequest):
        try:
            ruta = state.router.route(mensajes=body.messages, modelo_hint=body.model, task_hint=body.task)
            provider_name, modelo, route_reason = ruta.provider, ruta.modelo, ruta.route_reason
        except NoProviderAvailable as e:
            raise HTTPException(status_code=503, detail=str(e))  # noqa: B904
        _rechazar_si_bloqueado(provider_name, state.circuit_breaker, state.rate_limiter)

        if body.tools is True:
            herramientas = TOOL_SCHEMAS
        elif isinstance(body.tools, list):
            herramientas = body.tools
        else:
            herramientas = None

        is_opencode = body.force_guardian or "opencode" in body.model.lower()
        guardian = OpenCodeGuardian() if is_opencode else None
        if body.stream:
            return StreamingResponse(
                _stream_from_provider(
                    provider_name,
                    modelo,
                    body.messages,
                    herramientas,
                    body.max_tokens,
                    body.temperature,
                    state=state,
                    is_opencode=is_opencode,
                    guardian=guardian,
                ),
                media_type="text/event-stream",
                headers={
                    "X-Mochila-Provider": provider_name,
                    "X-Mochila-Modelo": modelo,
                    "X-Mochila-Route-Reason": route_reason,
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

        provider = state.providers[provider_name]
        respuesta = await _chat_no_stream(provider, modelo, body.messages, herramientas, body.max_tokens, body.temperature)
        if not respuesta:
            raise HTTPException(status_code=502, detail="Respuesta vacia del provider")
        state.circuit_breaker.registrar_exito(provider_name)
        state.rate_limiter.registrar(provider_name)
        _procesar_usage(respuesta, provider_name, modelo, state.cost_tracker)
        msg = respuesta.get("choices", [{}])[0].get("message", {})
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            mensajes_con_tool = list(body.messages)
            mensajes_con_tool.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": tool_calls})
            for tc in tool_calls:
                fid = tc.get("id", tc.get("index", "call_0"))
                fname = tc.get("function", {}).get("name", "")
                fargs_raw = tc.get("function", {}).get("arguments", "{}")
                try:
                    fargs = json.loads(fargs_raw) if isinstance(fargs_raw, str) else fargs_raw
                except json.JSONDecodeError:
                    fargs = {}
                resultado = await ejecutar_tool(fname, fargs)
                mensajes_con_tool.append(
                    {"role": "tool", "tool_call_id": fid, "content": json.dumps(resultado, ensure_ascii=False)},
                )
            respuesta_final = await _chat_no_stream(
                provider,
                modelo,
                mensajes_con_tool,
                herramientas,
                body.max_tokens,
                body.temperature,
            )
            if respuesta_final:
                respuesta = respuesta_final
                _procesar_usage(respuesta_final, provider_name, modelo, state.cost_tracker)

        return JSONResponse(
            content=respuesta,
            headers={
                "X-Mochila-Provider": provider_name,
                "X-Mochila-Modelo": modelo,
                "X-Mochila-Route-Reason": route_reason,
            },
        )

    return router
