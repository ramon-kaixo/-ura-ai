import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from core.mochila.providers import GeminiProvider, OllamaProvider, OpenRouterProvider, ProviderError

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


def _now() -> int:
    return int(time.time())


def _estimar_tokens(texto: str) -> int:
    return len(texto) // 4


def _clasificar_peticion(mensajes: list, task: str | None) -> str:
    if task and task in ("codigo", "razonamiento", "rapido"):
        return task

    texto = " ".join(m.get("content", "") for m in mensajes).lower()

    patrones = {
        "codigo": [
            "refactor", "funcion", "clase", "import", "def ", "bug", "fix",
            "test", "type", "codigo", "implementa", "bash", "script",
            "terminal", "git", "commit", "push", "pip",
        ],
        "razonamiento": [
            "analiza", "compara", "evalua", "planea", "arquitectura",
            "estrategia", "diseno", "sistema", "impacto", "pros y contras",
            "recomienda", "que es mejor",
        ],
    }

    puntuaciones: dict[str, int] = {"codigo": 0, "razonamiento": 0}
    for tipo, palabras in patrones.items():
        for p in palabras:
            if p in texto:
                puntuaciones[tipo] += 1

    if puntuaciones["codigo"] > puntuaciones["razonamiento"]:
        return "codigo"
    elif puntuaciones["razonamiento"] > puntuaciones["codigo"]:
        return "razonamiento"
    return "rapido"


RUTAS: dict[str, list[dict]] = {
    "codigo": [
        {"provider": "ollama", "modelo": "qwen2.5-coder:32b"},
        {"provider": "openrouter", "modelo": "anthropic/claude-sonnet-4"},
        {"provider": "openrouter", "modelo": "deepseek/deepseek-v4-flash"},
    ],
    "razonamiento": [
        {"provider": "openrouter", "modelo": "google/gemini-2.5-flash"},
        {"provider": "ollama", "modelo": "qwen3:32b-q8_0"},
        {"provider": "openrouter", "modelo": "anthropic/claude-sonnet-4"},
    ],
    "rapido": [
        {"provider": "ollama", "modelo": "qwen2.5:7b"},
        {"provider": "openrouter", "modelo": "deepseek/deepseek-v4-flash"},
    ],
}


class NoProviderAvailable(Exception):
    ...


def _elegir_provider(tipo: str, modelo_especifico: str | None) -> tuple[str, str, str]:
    if modelo_especifico and modelo_especifico != "auto":
        if "/" in modelo_especifico:
            p, m = modelo_especifico.split("/", 1)
            if p in PROVIDERS:
                return p, m, f"explicit:{modelo_especifico}"
        return "ollama", modelo_especifico, f"explicit:{modelo_especifico}"

    for entrada in RUTAS.get(tipo, RUTAS["rapido"]):
        p = entrada["provider"]
        if p in PROVIDERS:
            return p, entrada["modelo"], f"keyword:{tipo}"

    raise NoProviderAvailable(f"Ningún provider disponible para tipo={tipo}")


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
                return
            yield b"data: " + json.dumps(chunk).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    except asyncio.TimeoutError:
        yield b"data: " + json.dumps({
            "error": {"message": f"Timeout ({timeout_val}s) del provider {provider_name}", "type": "timeout_error"}
        }).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    except ProviderError as e:
        yield b"data: " + json.dumps({
            "error": {"message": str(e), "type": "provider_error", "provider": provider_name}
        }).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    except Exception as e:
        yield b"data: " + json.dumps({
            "error": {"message": f"Error inesperado: {str(e)}", "type": "internal_error"}
        }).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for p in PROVIDERS.values():
        if hasattr(p, "__aenter__"):
            await p.__aexit__(None, None, None)


app = FastAPI(
    title="Mochila Middleware",
    version="0.1.0",
    description="Middleware de routing multi-provider + tool injection",
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

    for tipo, ruta in RUTAS.items():
        for entrada in ruta:
            mid = f"{entrada['provider']}/{entrada['modelo']}"
            if not any(m["id"] == mid for m in models):
                models.append({"id": mid, "provider": entrada["provider"], "object": "model"})

    CACHE_MODELS = models
    CACHE_MODELS_TS = time.time()
    return {"object": "list", "data": models}


@app.post("/v1/chat/completions")
async def v1_chat_completions(body: ChatRequest):
    tipo = _clasificar_peticion(body.messages, body.task)
    try:
        provider_name, modelo, route_reason = _elegir_provider(tipo, body.model if body.model != "auto" else None)
    except NoProviderAvailable as e:
        raise HTTPException(status_code=503, detail=str(e))

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
    timeout_val = PROVIDER_TIMEOUTS.get(provider_name, 60)
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
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))

    return JSONResponse(
        content=respuesta,
        headers={
            "X-Mochila-Provider": provider_name,
            "X-Mochila-Modelo": modelo,
            "X-Mochila-Route-Reason": route_reason,
        },
    )


@app.get("/metrics")
async def metrics():
    return {
        "providers": list(PROVIDERS.keys()),
        "timeouts": PROVIDER_TIMEOUTS,
        "rutas": {k: [e["provider"] + "/" + e["modelo"] for e in v] for k, v in RUTAS.items()},
        "clasificador": "keyword",
    }
