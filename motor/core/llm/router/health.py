"""Health check with caching for LLM router."""

from __future__ import annotations

import threading
import time
from contextlib import suppress
from typing import Any

from motor.core.llm.router.utils import _classify_error


def health_get_cached(
    name: str,
    health_cache: dict[str, tuple[float, dict[str, Any] | None]],
    health_lock: threading.Lock,
    health_cache_ttl: float,
) -> dict[str, Any] | None:
    health_lock.acquire()
    try:
        entry = health_cache.get(name)
        if entry is not None:
            cached_at, cached_result = entry
            if cached_result is not None and time.monotonic() - cached_at < health_cache_ttl:
                return cached_result
            if cached_result is None:
                for _ in range(20):
                    health_lock.release()
                    time.sleep(0.005)
                    health_lock.acquire()
                    entry2 = health_cache.get(name)
                    if entry2 is not None and entry2[1] is not None:
                        return entry2[1]
        health_cache[name] = (0.0, None)
        return None
    finally:
        with suppress(RuntimeError):
            health_lock.release()


def health_store_cache(
    name: str,
    result: dict[str, Any],
    health_cache: dict[str, tuple[float, dict[str, Any] | None]],
    health_lock: threading.Lock,
) -> None:
    with health_lock:
        health_cache[name] = (time.monotonic(), result)


def health_remove_cache(
    name: str,
    health_cache: dict[str, tuple[float, dict[str, Any] | None]],
    health_lock: threading.Lock,
) -> None:
    with health_lock:
        health_cache.pop(name, None)
