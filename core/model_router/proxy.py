"""Proxy — funciones de proxy a Ollama con soporte VRAM, failover y telemetría."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

_fallback_log: deque[float] = deque(maxlen=3600)
_fallback_lock = threading.Lock()
_asus_latency_ms: float = 0.0
_asus_latency_updated: float = 0.0
_asus_latency_lock = threading.Lock()

_CONTEXT_WARN_THRESHOLD = 12000
_CONTEXT_SUMMARY_THRESHOLD = 24000
_CHARS_PER_TOKEN = 4.0


def _register_fallback() -> None:
    with _fallback_lock:
        _fallback_log.append(time.time())


def _fallback_count_last_hour() -> int:
    now = time.time()
    with _fallback_lock:
        cutoff = now - 3600
        while _fallback_log and _fallback_log[0] < cutoff:
            _fallback_log.popleft()
        return len(_fallback_log)


def _measare_asus_latency() -> float:
    from core.model_router.router import _URLS
    try:
        t0 = time.monotonic()
        req = urllib.request.Request(f"{_URLS['primary']}/api/tags")  # noqa: S310
        req.add_header("Connection", "close")
        with urllib.request.urlopen(req, timeout=5):  # noqa: S310
            elapsed = (time.monotonic() - t0) * 1000
            return round(elapsed, 1)
    except Exception:
        return -1.0


def _update_asus_latency() -> None:
    global _asus_latency_ms, _asus_latency_updated  # noqa: PLW0603
    ms = _measare_asus_latency()
    with _asus_latency_lock:
        _asus_latency_ms = ms
        _asus_latency_updated = time.time()


def _get_active_backend_label() -> str:
    from core.model_router.router import POWER_MODE
    if POWER_MODE == "TURBO":
        return "ASUS Remoto"
    if POWER_MODE == "ECO":
        return "Local Mac"
    return "AUTO (según IP)"


def _estimate_tokens(text: str) -> int:
    return int(len(text) / _CHARS_PER_TOKEN)


def _check_context_size(messages: list[dict] | list | str | None) -> dict:
    text = ""
    if isinstance(messages, str):
        text = messages
    elif isinstance(messages, list):
        text = " ".join(msg.get("content", "") if isinstance(msg, dict) else str(msg) for msg in messages)
    chars = len(text)
    tokens = _estimate_tokens(text)
    if tokens >= _CONTEXT_SUMMARY_THRESHOLD:
        return {
            "tokens": tokens,
            "chars": chars,
            "level": "critical",
            "message": f"Contexto muy grande ({tokens} tokens). Se recomienda resumir antes de enviar.",
        }
    if tokens >= _CONTEXT_WARN_THRESHOLD:
        return {
            "tokens": tokens,
            "chars": chars,
            "level": "warn",
            "message": f"Contexto grande ({tokens} tokens). Considera reducir el prompt.",
        }
    return {"tokens": tokens, "chars": chars, "level": "ok", "message": f"Contexto normal ({tokens} tokens)."}


def _is_local_ip(ip: str) -> bool:
    local_prefixes = (
        "127.",
        "10.",
        "192.168.",
        "172.16.",
        "172.17.",
        "172.18.",
        "172.19.",
        "172.20.",
        "172.21.",
        "172.22.",
        "172.23.",
        "172.24.",
        "172.25.",
        "172.26.",
        "172.27.",
        "172.28.",
        "172.29.",
        "172.30.",
        "172.31.",
    )
    return ip.startswith(local_prefixes)


def _resolve_mode_for_client(client_ip: str) -> str:
    from core.model_router.router import POWER_MODE
    if POWER_MODE == "TURBO":
        return "TURBO"
    if POWER_MODE == "ECO":
        return "ECO"
    if _is_local_ip(client_ip):
        return "TURBO"
    return "ECO"


def _resolve_ollama_url() -> str:
    from core.model_router.router import _URLS
    env_url = os.environ.get("OLLAMA_URL")
    if env_url:
        log.info("OLLAMA_URL forzada por env: %s", env_url)
        return env_url
    try:
        req = urllib.request.Request(f"{_URLS['primary']}/api/tags")  # noqa: S310
        req.add_header("Connection", "close")
        with urllib.request.urlopen(req, timeout=5) as _:  # noqa: S310
            log.info("ASUS conectado: %s", _URLS["primary"])
            return _URLS["primary"]
    except Exception as e:
        log.warning("ASUS no accesible en startup: %s", e)
        return _URLS["fallback"]


async def _proxy_con_guardia_vram(path, body, method="POST", modelo="", tipo="", client_ip=""):
    from core.model_router.vram_guard import vram_guard
    return await vram_guard.ejecutar_inferencia_segura(
        _proxy_request_async,
        path,
        body,
        method,
        modelo,
        tipo,
        client_ip,
    )


async def _proxy_request_async(path, body, method="POST", modelo="", tipo="", client_ip=""):
    log.debug("[VRAM] Inferencia: modelo=%s, tipo=%s", modelo, tipo)
    import asyncio as _asyncio
    return await _asyncio.to_thread(proxy_request, path, body, method, modelo, tipo, client_ip)


def _proxy_con_vram(path, body, method="POST", modelo="", tipo="", client_ip=""):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_proxy_con_guardia_vram(path, body, method, modelo, tipo, client_ip))
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, _proxy_con_guardia_vram(path, body, method, modelo, tipo, client_ip))
        return future.result()


def proxy_request(
    path: str,
    body: bytes | None,
    method: str = "POST",
    modelo: str = "",
    tipo: str = "",
    client_ip: str = "",
) -> tuple:
    from core.model_router.metrics import metrics
    from core.model_router.model_selection import _record_success
    from core.model_router.router import _URLS

    resolved_mode = _resolve_mode_for_client(client_ip or "127.0.0.1")
    active_url = _URLS["primary"] if resolved_mode == "TURBO" else _URLS["fallback"]
    url = f"{active_url}{path}"
    req = urllib.request.Request(url, data=body if method == "POST" else None, method=method)  # noqa: S310
    req.add_header("Content-Type", "application/json")

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
            latency = time.time() - start_time
            metrics.record_latency("ollama_request", latency)
            if modelo and tipo:
                _record_success(modelo, tipo, ok=True)
                metrics.increment("model_success", {"modelo": modelo, "tipo": tipo})
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        latency = time.time() - start_time
        metrics.record_error("ollama_request", "http_error", {"status": str(e.code)})
        if modelo and tipo:
            _record_success(modelo, tipo, ok=False)
            metrics.increment("model_error", {"modelo": modelo, "tipo": tipo})
        return e.code, {}, e.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        latency = time.time() - start_time
        if resolved_mode == "TURBO":
            log.critical("ASUS FALLIDA (%s) — cliente local sin fallback", type(e).__name__)
        else:
            log.warning("Backend local caido (%s)", type(e).__name__)
        metrics.record_error("ollama_request", type(e).__name__)
        _register_fallback()
        if modelo and tipo:
            _record_success(modelo, tipo, ok=False)
            metrics.increment("model_error", {"modelo": modelo, "tipo": tipo})
        msg = f"Backend {'ASUS' if resolved_mode == 'TURBO' else 'local'} caido: {e}"
        return 503, {}, json.dumps({"error": msg}).encode()
    except Exception as e:
        latency = time.time() - start_time
        metrics.record_error("ollama_request", type(e).__name__)
        if modelo and tipo:
            _record_success(modelo, tipo, ok=False)
            metrics.increment("model_error", {"modelo": modelo, "tipo": tipo})
        error_body = json.dumps({"error": str(e)}).encode()
        return 502, {}, error_body
