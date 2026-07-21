"""PromptCache — caché de prompts con TTL y métricas."""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any

from core.model_router.metrics import metrics

CACHE_TTL = 7200


class PromptCache:
    def __init__(self, ttl: int = CACHE_TTL) -> None:
        self.cache: dict[str, dict[str, Any]] = {}
        self.ttl = ttl
        self.lock = threading.Lock()

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, prompt: str, tipo: str) -> dict | None:
        key = self._hash_content(f"{tipo}:{prompt}")
        with self.lock:
            if key in self.cache:
                cached = self.cache[key]
                if time.time() - cached["timestamp"] < self.ttl:
                    metrics.increment("prompt_cache_hit", {"tipo": tipo})
                    return cached["response"]
                del self.cache[key]
        metrics.increment("prompt_cache_miss", {"tipo": tipo})
        return None

    def set(self, prompt: str, tipo: str, response: dict) -> None:
        key = self._hash_content(f"{tipo}:{prompt}")
        with self.lock:
            self.cache[key] = {"response": response, "timestamp": time.time()}

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()


prompt_cache = PromptCache()
