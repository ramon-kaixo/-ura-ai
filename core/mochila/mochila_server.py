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
from core.mochila.providers import GeminiProvider, OllamaProvider, OpenRouterProvider, ProviderError, GroqProvider, DeepSeekProvider
from core.mochila.rate_limiter import RateLimiter
from core.mochila.router import NoProviderAvailable, Router
from core.mochila.tools import TOOL_SCHEMAS, ejecutar_tool
from core.memoria.consulta import consultar as memoria_consultar
from core.memoria.ingesto import procesar_inbox_completo
from core.memoria.extractores.video_pipeline import pipeline_video
from core.memoria.analizador import analizar
from core.memoria.sintetizador import sintetizar
from core.mochila.guardian_middleware import GuardianMiddleware, init_guardian
from core.mochila.guardian_middleware import GuardianMiddleware, init_guardian
from core.mochila.guardian_middleware import GuardianMiddleware, init_guardian
from core.memoria.rastreadores.saber import fase_saber
from core.memoria.rastreadores.hacer import fase_hacer
from core.memoria.rastreadores.comprar import fase_comprar
from core.memoria.vigilante import generar_parte

load_dotenv(os.path.expanduser("~/URA/.env"))

PROVIDERS: dict[str, OllamaProvider | OpenRouterProvider | GeminiProvider] = {
    "ollama": OllamaProvider(),
    "openrouter": OpenRouterProvider(),
    "gemini": GeminiProvider(),
    "groq": GroqProvider(),
    "deepseek": DeepSeekProvider(),
}
PROVIDER_TIMEOUTS: dict[str, int] = {"ollama": 180, "openrouter": 60, "gemini": 60,
    "groq": 60,
    "deepseek": 60}
CACHE_MODELS: list = []
CACHE_MODELS_TS: float = 0

router = Router(providers=PROVIDERS)
circuit_breaker = CircuitBreaker()
rate_limiter = RateLimiter()
cost_tracker = CostTracker()


class ChatRequest(BaseModel):
    model: str = Field(default="auto")
    messages: list
    stream: bool = False
    tools: list | bool | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    task: str | None = None


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
        raise HTTPException(status_code=503, detail={"error": f"Circuit breaker OPEN para {provider_name}", "state": h["state"]})
    puede, actual, limite = rate_limiter.puede_pasar(provider_name)
    if not puede:
        raise HTTPException(status_code=429, detail={"error": f"Rate limit excedido para {provider_name}", "current": actual, "limit": limite})


def _procesar_usage(respuesta: dict | None, provider_name: str, modelo: str) -> None:
    if respuesta and isinstance(respuesta, dict):
        uso = respuesta.get("usage") or {}
        cost_tracker.registrar(provider_name, modelo, uso.get("prompt_tokens", 0) or 0, uso.get("completion_tokens", 0) or 0)


async def _chat_no_stream(provider, modelo, mensajes, herramientas, max_tokens, temperature) -> dict | None:
    try:
        async for chunk in provider.chat(modelo=modelo, mensajes=mensajes, stream=False, tools=herramientas, max_tokens=max_tokens, temperature=temperature):
            return chunk
    except ProviderError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=f"{e.provider}: {e}")
    return None


async def _stream_from_provider(provider_name, modelo, mensajes, herramientas, max_tokens, temperature) -> AsyncGenerator[bytes, None]:
    provider = PROVIDERS[provider_name]
    timeout_val = PROVIDER_TIMEOUTS.get(provider_name, 60)
    hubo_error = False
    try:
        gen = provider.chat(modelo=modelo, mensajes=mensajes, stream=True, tools=herramientas, max_tokens=max_tokens, temperature=temperature)
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
    except asyncio.TimeoutError:
        hubo_error = True
        circuit_breaker.registrar_fallo(provider_name, es_timeout=True)
        yield b"data: " + json.dumps({"error": {"message": f"Timeout ({timeout_val}s)", "type": "timeout_error"}}).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    except ProviderError as e:
        hubo_error = True
        circuit_breaker.registrar_fallo(provider_name)
        yield b"data: " + json.dumps({"error": {"message": str(e), "type": "provider_error"}}).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    except Exception as e:
        hubo_error = True
        circuit_breaker.registrar_fallo(provider_name)
        yield b"data: " + json.dumps({"error": {"message": f"Error: {str(e)}", "type": "internal_error"}}).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    finally:
        if not hubo_error:
            circuit_breaker.registrar_exito(provider_name)
            rate_limiter.registrar(provider_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_guardian()
    yield
    for p in PROVIDERS.values():
        if hasattr(p, "__aenter__"):
            await p.__aexit__(None, None, None)


app = FastAPI(title="Mochila Middleware", version="0.7.0", lifespan=lifespan)
app.add_middleware(GuardianMiddleware)
app.add_middleware(GuardianMiddleware)
app.add_middleware(GuardianMiddleware)


@app.get("/health")
async def health():
    return {"status": "ok", "providers": {name: await provider.health() for name, provider in PROVIDERS.items()}}


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
        provider_name, modelo, route_reason = ruta.provider, ruta.modelo, ruta.route_reason
    except NoProviderAvailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    _rechazar_si_bloqueado(provider_name)

    if body.tools is True:
        herramientas = TOOL_SCHEMAS
    elif isinstance(body.tools, list):
        herramientas = body.tools
    else:
        herramientas = None

    if body.stream:
        return StreamingResponse(
            _stream_from_provider(provider_name, modelo, body.messages, herramientas, body.max_tokens, body.temperature),
            media_type="text/event-stream",
            headers={"X-Mochila-Provider": provider_name, "X-Mochila-Modelo": modelo, "X-Mochila-Route-Reason": route_reason, "Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    provider = PROVIDERS[provider_name]
    respuesta = await _chat_no_stream(provider, modelo, body.messages, herramientas, body.max_tokens, body.temperature)
    if not respuesta:
        raise HTTPException(status_code=502, detail="Respuesta vacia del provider")
    circuit_breaker.registrar_exito(provider_name)
    rate_limiter.registrar(provider_name)
    _procesar_usage(respuesta, provider_name, modelo)

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
            mensajes_con_tool.append({"role": "tool", "tool_call_id": fid, "content": json.dumps(resultado, ensure_ascii=False)})
        respuesta_final = await _chat_no_stream(provider, modelo, mensajes_con_tool, herramientas, body.max_tokens, body.temperature)
        if respuesta_final:
            respuesta = respuesta_final
            _procesar_usage(respuesta_final, provider_name, modelo)

    return JSONResponse(content=respuesta, headers={"X-Mochila-Provider": provider_name, "X-Mochila-Modelo": modelo, "X-Mochila-Route-Reason": route_reason})


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

class VideoIngestRequest(BaseModel):
    path: str

@app.post("/memoria/ingestar/video")
async def memoria_ingestar_video(body: VideoIngestRequest):
    from pathlib import Path
    ruta = Path(body.path)
    if not ruta.exists():
        raise HTTPException(status_code=404, detail=f"No encontrado: {body.path}")
    return pipeline_video(ruta)


class AnalizarRequest(BaseModel):
    peticion: str

@app.post("/memoria/analizar")
async def memoria_analizar(body: AnalizarRequest):
    return await analizar(body.peticion)


class SintesisRequest(BaseModel):
    peticion: str

@app.post("/memoria/sintetizar")
async def memoria_sintetizar(body: SintesisRequest):
    return await sintetizar(body.peticion)


class FaseRequest(BaseModel):
    keywords: str

@app.post("/memoria/fase/saber")
async def memoria_fase_saber(body: FaseRequest):
    return await fase_saber(body.keywords)

@app.post("/memoria/fase/hacer")
async def memoria_fase_hacer(body: FaseRequest):
    return await fase_hacer(body.keywords)

@app.post("/memoria/fase/comprar")
async def memoria_fase_comprar(body: FaseRequest):
    return await fase_comprar(body.keywords)


@app.get("/memoria/vigilancia/parte")
async def memoria_vigilancia_parte():
    return await generar_parte()

@app.get("/metrics")
async def metrics():
    return {
        "providers": list(PROVIDERS.keys()),
        "timeouts": PROVIDER_TIMEOUTS,
        "rutas": {k: [e["provider"] + "/" + e["modelo"] for e in v] for k, v in router.rutas.items()},
        "clasificador": type(router.clasificador).__name__,
        "circuit_breaker": {p: circuit_breaker.estado(p) for p in PROVIDERS},
        "cost_hoy": cost_tracker.resumen_hoy(),
        "tools_disponibles": len(TOOL_SCHEMAS),
    }


class ConsultaRequest(BaseModel):
    query: str
    forzar_web: bool = False


@app.post("/memoria/consultar")
async def memoria_consultar_endpoint(body: ConsultaRequest):
    return await memoria_consultar(body.query, body.forzar_web)


@app.get("/memoria/health")
async def memoria_health():
    try:
        from core.memoria.qdrant_store import _get_client
        client = _get_client()
        info = client.get_collection("ideas")
        return {
            "status": "ok",
            "coleccion": "ideas",
            "puntos": info.points_count,
            "vectores": str(info.config.params.vectors),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/memoria/ingestar")
async def memoria_ingestar():
    return await procesar_inbox_completo()
