"""Proxy gateway a Ollama — mantiene HTTP directo por ser un proxy genérico.

EXCEPCIÓN: No se migra a motor.core.llm porque:
1. Es un proxy HTTP genérico (cualquier path: /api/chat, /api/tags, /api/show...)
2. Soporta streaming SSE (motor.core.llm.generate() es síncrono)
3. Las responses se devuelven tal cual (JSON passthrough)
   motor.core.llm no expone estas capacidades.
"""

import json
from contextlib import suppress

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from core.logs.guardian_logger import log_event
from core.mochila.guardian_opencode import OpenCodeGuardian
from core.mochila.vram_scheduler import OLLAMA_SOCKET


def create_proxy_router(state) -> APIRouter:
    router = APIRouter()

    @router.api_route("/api/{path:path}", methods=["GET", "POST"])
    async def proxy_gateway(path: str, request: Request):
        body = None
        with suppress(Exception):
            body = await request.json() if request.method in ("POST", "PUT") else None
        mb = state.scheduler.estimar_vram(body or {})
        req_id = await state.scheduler.acquire(
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

            is_opencode = (body or {}).get("_force_guardian", False) or "opencode" in (body or {}).get(
                "model", ""
            ).lower()
            guardian = OpenCodeGuardian() if is_opencode else None
            is_gen = path.endswith(("chat", "generate"))
            is_stream = (body or {}).get("stream", True)

            if is_gen and is_stream:

                async def _proxy_stream():
                    acc = ""
                    async with httpx.AsyncClient(timeout=180.0, base_url=OLLAMA_SOCKET) as c:  # noqa: SIM117
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
                resp = await client.post(
                    request.url.path, json=body, params=dict(request.query_params), headers=headers
                )
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.ConnectError as e:
            return JSONResponse(status_code=502, content={"error": f"Ollama connect error: {e}"})
        finally:
            await state.scheduler.release(req_id)

    return router
