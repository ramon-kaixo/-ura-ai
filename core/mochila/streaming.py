import json
import logging
from collections.abc import AsyncGenerator

from core.logs.guardian_logger import log_event
from core.mochila.helpers import _procesar_usage

log = logging.getLogger(__name__)


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
            if (
                chunk.get("choices")
                and chunk["choices"][0].get("delta", {}) == {}
                and chunk["choices"][0].get("finish_reason")
            ):
                yield b"data: [DONE]\n\n"
                state.circuit_breaker.registrar_exito(provider_name)
                state.rate_limiter.registrar(provider_name)
                _procesar_usage(chunk, provider_name, modelo, state.cost_tracker)
                return
            if is_opencode and guardian:
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    accumulated_text += delta
                    if not guardian.evaluar_texto_stream(accumulated_text):
                        penalty = guardian.generar_penalizacion()
                        payload = {"error": {"message": "STREAM_ABORTED_BY_GUARDIAN", "type": "vagancy_error"}}
                        if penalty:
                            payload["error"]["penalty_context"] = penalty
                        log_event(
                            "stream_aborted",
                            model=modelo,
                            file="",
                            reason="vagancy",
                            attempts=0,
                            penalty=penalty,
                        )
                        yield b"data: " + json.dumps(payload).encode() + b"\n\n"
                        yield b"data: [DONE]\n\n"
                        return
            yield b"data: " + json.dumps(chunk).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    except TimeoutError:
        hubo_error = True
        state.circuit_breaker.registrar_fallo(provider_name, es_timeout=True)
        yield (
            b"data: "
            + json.dumps({"error": {"message": f"Timeout ({timeout_val}s)", "type": "timeout_error"}}).encode()
            + b"\n\n"
        )
        yield b"data: [DONE]\n\n"
    except Exception as e:
        hubo_error = True
        state.circuit_breaker.registrar_fallo(provider_name)
        yield (b"data: " + json.dumps({"error": {"message": f"{e}", "type": "provider_error"}}).encode() + b"\n\n")
        yield b"data: [DONE]\n\n"
    finally:
        if not hubo_error:
            state.circuit_breaker.registrar_exito(provider_name)
            state.rate_limiter.registrar(provider_name)
