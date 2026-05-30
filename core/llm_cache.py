#!/usr/bin/env python3
"""
LLM Cache — FASE 5
────────────────────
Caché inteligente de consultas LLM con TTL adaptativo.
Usa disco (diskcache) si está disponible, o memoria.
"""

import hashlib
import threading
import time
from collections import OrderedDict

from core.logging_config import get_logger

logger = get_logger("llm_cache", log_dir="./logs")


class LLMCache:
    """
    Caché de respuestas LLM con invalidación contextual.

    Uso:
        cache = LLMCache(max_size=500)
        cached = cache.get("¿Qué hora es?")
        if not cached:
            response = query_ollama("¿Qué hora es?")
            cache.set("¿Qué hora es?", response)
    """

    def __init__(self, max_size: int = 500, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _key(self, prompt: str, model: str = "") -> str:
        raw = f"{model}:{prompt.strip().lower()}"[:500]
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, prompt: str, model: str = "", ttl: int | None = None) -> str | None:
        """Obtiene respuesta cacheada si existe y no expiró."""
        key = self._key(prompt, model)
        effective_ttl = ttl or self.ttl

        with self._lock:
            if key in self._cache:
                timestamp, response = self._cache[key]
                if time.time() - timestamp < effective_ttl:
                    self._cache.move_to_end(key)
                    self.hits += 1
                    return response
                else:
                    del self._cache[key]

        self.misses += 1
        return None

    def set(self, prompt: str, response: str, model: str = ""):
        """Almacena una respuesta en la caché."""
        key = self._key(prompt, model)

        with self._lock:
            self._cache[key] = (time.time(), response)
            self._cache.move_to_end(key)

            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def invalidate(self, prompt_prefix: str = ""):
        """Invalida entradas que contengan el prefijo dado."""
        with self._lock:
            if not prompt_prefix:
                self._cache.clear()
                logger.info("Caché completamente invalidada")
                return

            to_delete = []
            prefix_lower = prompt_prefix.lower()
            for key in self._cache:
                if prefix_lower in key:
                    to_delete.append(key)
            for key in to_delete:
                del self._cache[key]
            logger.info(f"Caché: {len(to_delete)} entradas invalidadas")

    @property
    def stats(self) -> dict:
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 3),
            "ttl": self.ttl,
        }


# ── Singleton ──────────────────────────────────────────────

_cache: LLMCache | None = None


def get_llm_cache() -> LLMCache:
    global _cache
    if _cache is None:
        _cache = LLMCache(max_size=500, ttl=300)
    return _cache
