import asyncio
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from core.logs.guardian_logger import log_event
from core.memoria.analizador import analizar
from core.memoria.consulta import consultar as memoria_consultar
from core.memoria.ingesto import procesar_inbox_completo

log = logging.getLogger(__name__)
from core.memoria.rastreadores.comprar import fase_comprar
from core.memoria.rastreadores.hacer import fase_hacer
from core.memoria.rastreadores.saber import fase_saber
from core.memoria.sintetizador import sintetizar
from core.memoria.vigilante import generar_parte
from core.mochila.circuit_breaker import CircuitBreaker
from core.mochila.cost_tracker import CostTracker
from core.mochila.guardian_middleware import GuardianMiddleware, init_guardian
from core.mochila.guardian_opencode import OpenCodeGuardian
from core.mochila.providers import GeminiProvider, OllamaProvider, OpenRouterProvider, ProviderError
from core.mochila.rate_limiter import RateLimiter
from core.mochila.router import NoProviderAvailable, Router
from core.mochila.status_endpoint import system_status
from core.mochila.tools import TOOL_SCHEMAS, ejecutar_tool

load_dotenv(os.path.expanduser("~/URA/.env"))

OLLAMA_SOCKET = "http://127.0.0.1:11434"

PROVIDERS: dict[str, Any] = {
    "ollama": OllamaProvider(),
    "openrouter": OpenRouterProvider(),
    "gemini": GeminiProvider(),
}
PROVIDER_TIMEOUTS: dict[str, float] = {
    "ollama": 120.0,
    "openrouter": 60.0,
    "gemini": 30.0,
}
CACHE_MODELS: list = []
CACHE_MODELS_TS: float = 0


class VRAMAwareScheduler:
    def __init__(self, default_max_mb: int = 100000, queue_timeout: float = 60.0) -> None:
        self.max_mb = self._detect_max_vram(default_max_mb)
        self.queue_timeout = queue_timeout
        self._queue: list[tuple[asyncio.Future, int, float, dict[str, Any]]] = []
        self._active: dict[str, dict[str, Any]] = {}
        self._current_mb = 0
        self._hot_models: set = set()
        self._consecutive_smi_errors = 0
        self._lock = asyncio.Lock()
        self._ollama_client = httpx.AsyncClient(base_url=OLLAMA_SOCKET)
        self._log = logging.getLogger("mochila.vram")
        self._task: asyncio.Task | None = None

    @staticmethod
    def _detect_max_vram(default_mb: int) -> int:
        import subprocess

        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],  # noqa: S607  -- comando constante
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip() and "N/A" not in res.stdout:
                return int(res.stdout.strip())
        except Exception as e:
            log.warning("mochila: store_event falló: %s", e)
        return default_mb

    def available_mb(self) -> int:
        return self.max_mb - self._current_mb

    @staticmethod
    def estimar_vram(body: dict) -> int:
        if "_vram_mb" in body:
            return int(body["_vram_mb"])
        model = body.get("model", "")
        base_weights = {
            "qwen2.5-coder:32b": 18000,
            "qwen2.5-coder:14b": 9000,
            "qwen2-vl-7b": 6000,
            "llama3.2:3b": 2500,
        }
        base = base_weights.get(model, 512)
        prompt = body.get("prompt", "") or str(body.get("messages", ""))
        kv_cache_overhead = int((len(prompt) // 4) * 0.002)
        return base + kv_cache_overhead

    async def sync_vram(self) -> None:
        proc = None
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "nvidia-smi",
                    "--query-compute-apps=used_memory",
                    "--format=csv,noheader",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                ),
                timeout=0.2,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                total = 0
                for line in stdout.decode().strip().split("\n"):
                    if line.strip():
                        total += int(line.strip().split()[0])
                self._current_mb = total
                self._consecutive_smi_errors = 0
        except TimeoutError:
            self._consecutive_smi_errors += 1
            self._log.warning("nvidia-smi timeout (%d/3)", self._consecutive_smi_errors)
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception as e:
                    log.debug("mochila: rate limit get falló: %s", e)
        except Exception as e:
            self._consecutive_smi_errors += 1
            self._log.warning("nvidia-smi error (%d/3): %s", self._consecutive_smi_errors, e)
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception as e:
                    log.debug("mochila: rate limit get falló: %s", e)
        if self._consecutive_smi_errors >= 3:
            self._log.critical("nvidia-smi caido persistentemente. Bloqueando VRAM.")
            self._current_mb = self.max_mb
        try:
            resp = await self._ollama_client.get("/api/ps")
            if resp.status_code == 200:
                data = resp.json()
                self._hot_models = {m["name"] for m in data.get("models", [])}
        except Exception as e:
            log.warning("mochila: store_event falló: %s", e)

    async def acquire(self, mb: int, deadline_flex: float = 10.0, data: dict | None = None) -> str | None:
        async with self._lock:
            if len(self._active) > 0:
                return None
            if self.available_mb() < mb:
                future = asyncio.get_running_loop().create_future()
                deadline = time.time() + max(deadline_flex, 5.0)
                self._queue.append((future, mb, deadline, data or {}))
            else:
                req_id = str(uuid.uuid4())
                self._active[req_id] = {"mb": mb, "ts": time.time(), "model": (data or {}).get("model", "")}
                return req_id
        try:
            return await asyncio.wait_for(future, timeout=deadline_flex + 1.0)
        except TimeoutError:
            return None

    async def acquire_boot_vram(self, mb: int) -> bool:
        async with self._lock:
            future = asyncio.get_running_loop().create_future()
            self._queue.append((future, mb, time.time() + 120.0, {"model": "static_boot_service"}))
        try:
            req_id = await asyncio.wait_for(future, timeout=90.0)
        except TimeoutError:
            return False

        async def _release() -> None:
            try:
                await asyncio.sleep(3.0)
            finally:
                async with self._lock:
                    self._active.pop(req_id, None)

        asyncio.create_task(_release())
        return True

    async def release(self, req_id: str) -> None:
        async with self._lock:
            self._active.pop(req_id, None)

    async def start_loop(self) -> None:
        self._task = asyncio.create_task(self._scheduler_loop())

    async def stop_loop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _scheduler_loop(self) -> None:
        while True:
            try:
                await self.sync_vram()
                async with self._lock:
                    now = time.time()
                    self._queue = [(f, mb, dl, d) for f, mb, dl, d in self._queue if dl > now]
                    if len(self._active) == 0 and self._queue:
                        fut, mb, _deadline, data = self._queue[0]
                        if not fut.done() and mb <= self.available_mb():
                            self._queue.pop(0)
                            req_id = str(uuid.uuid4())
                            self._active[req_id] = {"mb": mb, "ts": now, "model": data.get("model", "")}
                            fut.set_result(req_id)
            except Exception as e:
                self._log.error("scheduler_loop error: %s", e)
            await asyncio.sleep(0.5)


scheduler = VRAMAwareScheduler()

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
    force_guardian: bool = False


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
            detail={"error": f"Circuit breaker OPEN para {provider_name}", "state": h["state"]},
        )
    puede, actual, limite = rate_limiter.puede_pasar(provider_name)
    if not puede:
        raise HTTPException(
            status_code=429,
            detail={"error": f"Rate limit excedido para {provider_name}", "current": actual, "limit": limite},
        )


def _procesar_usage(respuesta: dict | None, provider_name: str, modelo: str) -> None:
    if respuesta and isinstance(respuesta, dict):
        uso = respuesta.get("usage") or {}
        cost_tracker.registrar(
            provider_name,
            modelo,
            uso.get("prompt_tokens", 0) or 0,
            uso.get("completion_tokens", 0) or 0,
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
    except ProviderError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=f"{e.provider}: {e}")
    return None


async def _stream_from_provider(
    provider_name,
    modelo,
    mensajes,
    herramientas,
    max_tokens,
    temperature,
    is_opencode=False,
    guardian=None,
) -> AsyncGenerator[bytes, None]:
    provider = PROVIDERS[provider_name]
    timeout_val = PROVIDER_TIMEOUTS.get(provider_name, 60)
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
                circuit_breaker.registrar_exito(provider_name)
                rate_limiter.registrar(provider_name)
                _procesar_usage(chunk, provider_name, modelo)
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
        circuit_breaker.registrar_fallo(provider_name, es_timeout=True)
        yield (
            b"data: "
            + json.dumps({"error": {"message": f"Timeout ({timeout_val}s)", "type": "timeout_error"}}).encode()
            + b"\n\n"
        )
        yield b"data: [DONE]\n\n"
    except ProviderError as e:
        hubo_error = True
        circuit_breaker.registrar_fallo(provider_name)
        yield b"data: " + json.dumps({"error": {"message": str(e), "type": "provider_error"}}).encode() + b"\n\n"
        yield b"data: [DONE]\n\n"
    except Exception as e:
        hubo_error = True
        circuit_breaker.registrar_fallo(provider_name)
        yield (
            b"data: " + json.dumps({"error": {"message": f"Error: {e!s}", "type": "internal_error"}}).encode() + b"\n\n"
        )
        yield b"data: [DONE]\n\n"
    finally:
        if not hubo_error:
            circuit_breaker.registrar_exito(provider_name)
            rate_limiter.registrar(provider_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_guardian()
    await scheduler.start_loop()
    yield
    await scheduler.stop_loop()
    for p in PROVIDERS.values():
        if hasattr(p, "__aenter__"):
            await p.__aexit__(None, None, None)


app = FastAPI(title="Mochila Middleware", version="0.7.0", lifespan=lifespan)
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
    for ruta in router.rutas.values():
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
            _procesar_usage(respuesta_final, provider_name, modelo)

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


@app.post("/admin/acquire_boot_vram")
async def admin_acquire_boot_vram(mb: int):
    await scheduler.acquire_boot_vram(mb)
    return {"status": "granted"}


@app.api_route("/api/{path:path}", methods=["GET", "POST"])
async def proxy_gateway(path: str, request: Request):
    body = None
    with suppress(Exception):
        body = await request.json() if request.method in ("POST", "PUT") else None
    mb = scheduler.estimar_vram(body or {})
    req_id = await scheduler.acquire(
        mb=mb,
        deadline_flex=15.0,
        data={"model": body.get("model", "") if body else path.split("/", maxsplit=1)[0] if "/" in path else path},
    )
    if not req_id:
        return JSONResponse(
            status_code=503,
            content={"error": "VRAM admission denied", "detail": "No hay suficiente VRAM disponible"},
        )
    try:
        headers = {"Content-Type": "application/json"}
        auth = request.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth
        if request.method == "GET":
            async with httpx.AsyncClient(timeout=180.0, base_url=OLLAMA_SOCKET) as client:
                resp = await client.get(request.url.path, params=dict(request.query_params), headers=headers)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)

        is_opencode = (body or {}).get("_force_guardian", False) or "opencode" in (body or {}).get("model", "").lower()
        guardian = OpenCodeGuardian() if is_opencode else None
        is_gen = path.endswith(("chat", "generate"))
        is_stream = (body or {}).get("stream", True)

        if is_gen and is_stream:

            async def _proxy_stream():
                acc = ""
                async with httpx.AsyncClient(timeout=180.0, base_url=OLLAMA_SOCKET) as c:
                    async with c.stream("POST", request.url.path, json=body, headers=headers) as resp:
                        async for line in resp.aiter_lines():
                            if not line.strip():
                                yield line + "\n"
                                continue
                            if is_opencode and guardian:
                                try:
                                    data = json.loads(line)
                                    tok = (
                                        data.get("response", "")
                                        or data.get("message", {}).get("content", "")
                                        or data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    )
                                    if tok:
                                        acc += tok
                                        if not guardian.evaluar_texto_stream(acc):
                                            penalty = guardian.generar_penalizacion()
                                            err = {
                                                "error": {
                                                    "message": "STREAM_ABORTED_BY_GUARDIAN",
                                                    "type": "vagancy_error",
                                                },
                                            }
                                            if penalty:
                                                err["error"]["penalty_context"] = penalty
                                            log_event(
                                                "stream_aborted",
                                                model=body.get("model", ""),
                                                file=path,
                                                reason="vagancy",
                                                attempts=0,
                                                penalty=penalty,
                                            )
                                            yield json.dumps(err) + "\n"
                                            return
                                except json.JSONDecodeError:
                                    pass
                            yield line + "\n"

            return StreamingResponse(_proxy_stream(), media_type="application/x-ndjson")

        async with httpx.AsyncClient(timeout=180.0, base_url=OLLAMA_SOCKET) as client:
            resp = await client.post(request.url.path, json=body, params=dict(request.query_params), headers=headers)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError as e:
        return JSONResponse(status_code=502, content={"error": f"Ollama connect error: {e}"})
    finally:
        await scheduler.release(req_id)


class VideoIngestRequest(BaseModel):
    path: str


@app.post("/memoria/ingestar/video")
async def memoria_ingestar_video(body: VideoIngestRequest):
    from pathlib import Path

    ruta = Path(body.path)
    if not ruta.exists():
        raise HTTPException(status_code=404, detail=f"No encontrado: {body.path}")
    return {"status": "stub", "detail": "pipeline_video no implementado"}


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


@app.get("/status")
async def system_status_endpoint():
    return await system_status(PROVIDERS, cost_tracker, circuit_breaker, len(TOOL_SCHEMAS), router)


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
