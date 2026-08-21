"""Proxy gateway a Ollama — mantiene HTTP directo por ser un proxy genérico.

EXCEPCIÓN: No se migra a motor.core.llm porque:
1. Es un proxy HTTP genérico (cualquier path: /api/chat, /api/tags, /api/show...)
2. Soporta streaming SSE (motor.core.llm.generate() es síncrono)
3. Las responses se devuelven tal cual (JSON passthrough)
   motor.core.llm no expone estas capacidades.
"""

import json
import logging
from contextlib import suppress

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

log = logging.getLogger(__name__)

from core.logs.guardian_logger import log_event
from core.mochila.guardian_opencode import OpenCodeGuardian
from core.mochila.vram_scheduler import OLLAMA_SOCKET


def create_proxy_router(state) -> APIRouter:
    router = APIRouter()

    @router.api_route("/api/{path:path}", methods=["GET", "POST"])
    async def proxy_gateway(path: str, request: Request):
        body = await _leer_body(request)
        req_id = await _adquirir_vram(state, body, path)
        if req_id is None:
            return JSONResponse(
                status_code=503,
                content={"error": "VRAM admission denied", "detail": "No hay suficiente VRAM disponible"},
            )
        try:
            headers = _build_headers(request)
            if request.method == "GET":
                return await _get_upstream(request, headers)

            is_opencode = _es_opencode(body)
            guardian = OpenCodeGuardian() if is_opencode else None
            is_gen = path.endswith(("chat", "generate"))
            is_stream = (body or {}).get("stream", True)

            if is_gen and is_stream:
                return StreamingResponse(
                    _proxy_stream(request, body, headers, is_opencode, guardian, path),
                    media_type="application/x-ndjson",
                )

            return await _post_upstream(request, body, headers)
        except httpx.ConnectError as e:
            return JSONResponse(status_code=502, content={"error": f"Ollama connect error: {e}"})
        finally:
            await state.scheduler.release(req_id)

    return router


async def _leer_body(request: Request) -> dict | None:
    body = None
    with suppress(Exception):
        body = await request.json() if request.method in ("POST", "PUT") else None
    return body


async def _adquirir_vram(state, body: dict | None, path: str) -> str | None:
    mb = state.scheduler.estimar_vram(body or {})
    return await state.scheduler.acquire(
        mb=mb,
        deadline_flex=15.0,
        data={"model": body.get("model", "") if body else path.split("/", maxsplit=1)[0] if "/" in path else path},
    )


def _build_headers(request: Request) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth
    return headers


def _es_opencode(body: dict | None) -> bool:
    return (body or {}).get("_force_guardian", False) or "opencode" in (body or {}).get("model", "").lower()


async def _get_upstream(request: Request, headers: dict[str, str]) -> JSONResponse:
    async with httpx.AsyncClient(timeout=180.0, base_url=OLLAMA_SOCKET) as client:
        resp = await client.get(request.url.path, params=dict(request.query_params), headers=headers)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


async def _post_upstream(request: Request, body: dict | None, headers: dict[str, str]) -> JSONResponse:
    async with httpx.AsyncClient(timeout=180.0, base_url=OLLAMA_SOCKET) as client:
        resp = await client.post(request.url.path, json=body, params=dict(request.query_params), headers=headers)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


def _token_stream(data: dict) -> str:
    return (
        data.get("response", "")
        or data.get("message", {}).get("content", "")
        or data.get("choices", [{}])[0].get("delta", {}).get("content", "")
    )


def _error_guardian(penalty: str | None) -> dict:
    err = {"error": {"message": "STREAM_ABORTED_BY_GUARDIAN", "type": "vagancy_error"}}
    if penalty:
        err["error"]["penalty_context"] = penalty
    return err


def _log_stream_abort(body: dict | None, path: str, penalty: str | None) -> None:
    log_event(
        "stream_aborted",
        model=(body or {}).get("model", ""),
        file=path,
        reason="vagancy",
        attempts=0,
        penalty=penalty or "",
    )


async def _proxy_stream(
    request: Request,
    body: dict | None,
    headers: dict[str, str],
    is_opencode: bool,
    guardian: OpenCodeGuardian | None,
    path: str,
):
    acc = ""
    async with httpx.AsyncClient(timeout=180.0, base_url=OLLAMA_SOCKET) as c:  # noqa: SIM117
        async with c.stream("POST", request.url.path, json=body, headers=headers) as resp:
            async for line in resp.aiter_lines():
                if not line.strip():
                    yield line + "\n"
                    continue
                if is_opencode and guardian:
                    try:
                        tok = _token_stream(json.loads(line))
                        if tok:
                            acc += tok
                            if not guardian.evaluar_texto_stream(acc):
                                penalty = guardian.generar_penalizacion()
                                _log_stream_abort(body, path, penalty)
                                yield json.dumps(_error_guardian(penalty)) + "\n"
                                return
                    except json.JSONDecodeError as exc:
                        log.debug("chunk no-JSON en stream %s: %s", path, exc)
                        pass
                yield line + "\n"
