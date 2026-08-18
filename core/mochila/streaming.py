import json
import logging
from collections.abc import AsyncGenerator

from core.logs.guardian_logger import log_event
from core.mochila.helpers import _procesar_usage

log = logging.getLogger(__name__)


def _chunk_es_fin(chunk: dict) -> bool:
    return bool(
        chunk.get("choices") and chunk["choices"][0].get("delta", {}) == {} and chunk["choices"][0].get("finish_reason")
    )


def _abortar_por_guardian(
    guardian,
    chunk: dict,
    accumulated_text: str,
    modelo: str,
) -> tuple[bool, str, dict]:
    """Evaluar chunk contra el guardián; abortar el stream si procede."""
    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
    if not delta:
        return False, accumulated_text, {}
    accumulated_text += delta
    if guardian.evaluar_texto_stream(accumulated_text):
        return False, accumulated_text, {}
    penalty = guardian.generar_penalizacion()
    log_event(
        "stream_aborted",
        model=modelo,
        file="",
        reason="vagancy",
        attempts=0,
        penalty=penalty,
    )
    payload = {"error": {"message": "STREAM_ABORTED_BY_GUARDIAN", "type": "vagancy_error"}}
    if penalty:
        payload["error"]["penalty_context"] = penalty
    return True, accumulated_text, payload


async def _emitir_error_sse(
    state,
    provider_name: str,
    message: str,
    error_type: str,
    es_timeout: bool = False,
) -> AsyncGenerator[bytes, None]:
    """Registrar fallo en circuit breaker y emitir error SSE + [DONE]."""
    if es_timeout:
        state.circuit_breaker.registrar_fallo(provider_name, es_timeout=True)
    else:
        state.circuit_breaker.registrar_fallo(provider_name)
    yield b"data: " + json.dumps({"error": {"message": message, "type": error_type}}).encode() + b"\n\n"
    yield b"data: [DONE]\n\n"


async def _stream_from_provider(
    provider_name,
    modelo,
    mensajes,
    herramientas,
    max_tokens,
    temperature,
    state,
    is_opencode=False,
    guardian=None,
) -> AsyncGenerator[bytes, None]:
    provider = state.providers[provider_name]
    timeout_val = state.provider_timeouts.get(provider_name, 60)
    hubo_error = False
    accumulated_text = ""
    try:
        gen = provider.chat(
            modelo=modelo,
            mensajes=mensajes,
            stream=True,
            tools=herramientas,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        async for chunk in gen:
            if not chunk:
                continue
            if _chunk_es_fin(chunk):
                yield b"data: [DONE]\n\n"
                state.circuit_breaker.registrar_exito(provider_name)
                state.rate_limiter.registrar(provider_name)
                _procesar_usage(chunk, provider_name, modelo, state.cost_tracker)
                return
            if is_opencode and guardian:
                abortar, accumulated_text, payload = _abortar_por_guardian(guardian, chunk, accumulated_text, modelo)
                if abortar:
                    yield b"data: " + json.dumps(payload).encode() + b"\n\n"
                    yield b"data: [DONE]\n\n"
                    return
            yield b"data: " + json.dumps(chunk).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    except TimeoutError:
        hubo_error = True
        async for sse in _emitir_error_sse(
            state, provider_name, f"Timeout ({timeout_val}s)", "timeout_error", es_timeout=True
        ):
            yield sse
    except Exception as e:
        hubo_error = True
        async for sse in _emitir_error_sse(state, provider_name, f"{e}", "provider_error"):
            yield sse
    finally:
        if not hubo_error:
            state.circuit_breaker.registrar_exito(provider_name)
            state.rate_limiter.registrar(provider_name)
