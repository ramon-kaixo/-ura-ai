import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from core.mochila.circuit_breaker import CircuitBreaker
from core.mochila.cost_tracker import CostTracker
from core.mochila.providers import GeminiProvider, OllamaProvider, OpenRouterProvider, ProviderError
from core.mochila.rate_limiter import RateLimiter
from core.mochila.router import NoProviderAvailable, Router

load_dotenv(os.path.expanduser("~/URA/.env"))


PROVIDERS: dict[str, OllamaProvider | OpenRouterProvider | GeminiProvider] = {
    "ollama": OllamaProvider(),
    "openrouter": OpenRouterProvider(),
    "gemini": GeminiProvider(),
}

PROVIDER_TIMEOUTS: dict[str, int] = {
    "ollama": 180,
    "openrouter": 60,
    "gemini": 60,
}

CACHE_MODELS: list = []
CACHE_MODELS_TS: float = 0

router = Router(providers=PROVIDERS)
circuit_breaker = CircuitBreaker()
rate_limiter = RateLimiter()
cost_tracker = CostTracker()


class ChatRequest(BaseModel):
    model: str = Field(default="auto", description="Modelo o 'auto' para routing automático")
    messages: list
    stream: bool = False
    tools: list | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    task: str | None = Field(default=None, description="Pista de clasificación: codigo|razonamiento|rapido")


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list
    usage: dict | None = None


def _generar_id() -> str:
    return f"mochila-{uuid.uuid4().hex[:12]}"


def _rechazar_si_bloqueado(provider_name: str) -> None:
    if not circuit_breaker.puede_pasar(provider_name):
        h = circuit_breaker.estado(provider_name)
        raise HTTPException(
            status_code=503,
            detail={
                "error": f"Circuit breaker OPEN para {provider_name}",
                "state": h["state"],
                "retry_after": max(0, 30.0 - (time.time() - h["last_failure_time"])),
            },
        )
    puede, actual, limite = rate_limiter.puede_pasar(provider_name)
    if not puede:
        raise HTTPException(
            status_code=429,
            detail={
                "error": f"Rate limit excedido para {provider_name}",
                "current": actual,
                "limit": limite,
                "window_seconds": 60,
            },
        )


def _procesar_usage(respuesta: dict | None, provider_name: str, modelo: str) -> None:
    if respuesta and isinstance(respuesta, dict):
        uso = respuesta.get("usage") or {}
        pt = uso.get("prompt_tokens", 0) or 0
        ct = uso.get("completion_tokens", 0) or 0
        cost_tracker.registrar(provider_name, modelo, pt, ct)


async def _stream_from_provider(
    provider_name: str,
    modelo: str,
    mensajes: list,
    herramientas: list | None,
    max_tokens: int,
    temperature: float,
) -> AsyncGenerator[bytes, None]:
    provider = PROVIDERS[provider_name]
    timeout_val = PROVIDER_TIMEOUTS.get(provider_name, 60)
    hubo_error = False

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
            if chunk.get("choices") and chunk["choices"][0].get("delta", {}) == {} and chunk["choices"][0].get("finish_reason"):
                yield b"data: [DONE]\n\n"
                circuit_breaker.registrar_exito(provider_name)
                rate_limiter.registrar(provider_name)
                _procesar_usage(chunk, provider_name, modelo)
                return
            yield b"data: " + json.dumps(chunk).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
        circuit_breaker.registrar_exito(provider_name)
        rate_limiter.registrar(provider_name)
    except asyncio.TimeoutError:
        hubo_error = True
        circuit_breaker.registrar_fallo(provider_name, es_timeout=True)
        yield b"data: " + json.dumps({
            "error": {"message": f"Timeout ({timeout_val}s) del provider {provider_name}", "type": "timeout_error"}
        }).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    except ProviderError as e:
        hubo_error = True
        circuit_breaker.registrar_fallo(provider_name)
        yield b"data: " + json.dumps({
            "error": {"message": str(e), "type": "provider_error", "provider": provider_name}
        }).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    except Exception as e:
        hubo_error = True
        circuit_breaker.registrar_fallo(provider_name)
        yield b"data: " + json.dumps({
            "error": {"message": f"Error inesperado: {str(e)}", "type": "internal_error"}
        }).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    finally:
        if not hubo_error:
            circuit_breaker.registrar_exito(provider_name)
            rate_limiter.registrar(provider_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for p in PROVIDERS.values():
        if hasattr(p, "__aenter__"):
            await p.__aexit__(None, None, None)


app = FastAPI(
    title="Mochila Middleware",
    version="0.2.0",
    description="Middleware de routing multi-provider + tool injection + circuit breaker",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    results = {}
    for name, provider in PROVIDERS.items():
        results[name] = await provider.health()
    return {"status": "ok", "providers": results}


@app.get("/v1/models")
async def v1_models():
    global CACHE_MODELS, CACHE_MODELS_TS
    if CACHE_MODELS and time.time() - CACHE_MODELS_TS < 60:
        return CACHE_MODELS

    models = []
    for name, provider in PROVIDERS.items():
        h = await provider.health()
        if h.get("status") == "ok" and "modelos_disponibles" in h:
            for m in h["modelos_disponibles"][:50]:
                models.append({"id": f"{name}/{m}", "provider": name, "object": "model"})
        models.append({"id": f"{name}/auto", "provider": name, "object": "model"})

    for tipo, ruta in router.rutas.items():
        for entrada in ruta:
            mid = f"{entrada['provider']}/{entrada['modelo']}"
            if not any(m["id"] == mid for m in models):
                models.append({"id": mid, "provider": entrada["provider"], "object": "model"})

    CACHE_MODELS = models
    CACHE_MODELS_TS = time.time()
    return {"object": "list", "data": models}


@app.post("/v1/chat/completions")
async def v1_chat_completions(body: ChatRequest):
    try:
        ruta = router.route(mensajes=body.messages, modelo_hint=body.model, task_hint=body.task)
        provider_name = ruta.provider
        modelo = ruta.modelo
        route_reason = ruta.route_reason
    except NoProviderAvailable as e:
        raise HTTPException(status_code=503, detail=str(e))

    _rechazar_si_bloqueado(provider_name)

    if body.stream:
        return StreamingResponse(
            _stream_from_provider(
                provider_name=provider_name,
                modelo=modelo,
                mensajes=body.messages,
                herramientas=body.tools,
                max_tokens=body.max_tokens,
                temperature=body.temperature,
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

    provider = PROVIDERS[provider_name]
    try:
        respuesta = None
        async for chunk in provider.chat(
            modelo=modelo,
            mensajes=body.messages,
            stream=False,
            tools=body.tools,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        ):
            respuesta = chunk
            break
    except ProviderError as e:
        circuit_breaker.registrar_fallo(provider_name)
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))

    circuit_breaker.registrar_exito(provider_name)
    rate_limiter.registrar(provider_name)
    _procesar_usage(respuesta, provider_name, modelo)

    return JSONResponse(
        content=respuesta,
        headers={
            "X-Mochila-Provider": provider_name,
            "X-Mochila-Modelo": modelo,
            "X-Mochila-Route-Reason": route_reason,
        },
    )


@app.get("/breaker")
async def breaker_status():
    return {p: circuit_breaker.estado(p) for p in PROVIDERS}


@app.post("/breaker/reset/{provider}")
async def breaker_reset(provider: str):
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Provider {provider} no encontrado")
    circuit_breaker.reset(provider)
    return {"status": "reset", "provider": provider}


@app.get("/metrics/rate/{provider}")
async def rate_limit_status(provider: str):
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Provider {provider} no encontrado")
    return rate_limiter.estado(provider)


@app.get("/metrics/cost")
async def cost_summary():
    return cost_tracker.resumen_hoy()


@app.get("/metrics")
async def metrics():
    return {
        "providers": list(PROVIDERS.keys()),
        "timeouts": PROVIDER_TIMEOUTS,
        "rutas": {k: [e["provider"] + "/" + e["modelo"] for e in v] for k, v in router.rutas.items()},
        "clasificador": type(router.clasificador).__name__,
        "circuit_breaker": {p: circuit_breaker.estado(p) for p in PROVIDERS},
        "cost_hoy": cost_tracker.resumen_hoy(),
    }
