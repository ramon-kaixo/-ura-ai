"""OllamaEmbedder — implementa Embedder(Protocol) usando motor.core.llm.

Cache LRU in-process con TTL configurable.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict

from motor.core.llm import embed as _embed
from motor.core.llm import health as _health

log = logging.getLogger("ura.knowledge.vector_ollama")


class _LRUCache:
    """Cache LRU simple con TTL. No thread-safe (uso interno embebido)."""

    def __init__(self, ttl: int = 300, maxsize: int = 1024):
        self._ttl = ttl
        self._maxsize = maxsize
        self._cache: OrderedDict[str, tuple[float, list[float]]] = OrderedDict()

    def get(self, key: str) -> list[float] | None:
        if key not in self._cache:
            return None
        timestamp, value = self._cache[key]
        if time.monotonic() - timestamp > self._ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return value

    def put(self, key: str, value: list[float]) -> None:
        self._cache[key] = (time.monotonic(), value)
        self._cache.move_to_end(key)
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class OllamaEmbedder:
    """Embedder usando motor.core.llm para embeddings.

    Args:
        model: Nombre del modelo en Ollama.
        cache_ttl: TTL del cache LRU en segundos.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        cache_ttl: int = 300,
    ):
        self._model = model
        self._cache = _LRUCache(ttl=cache_ttl)
        self._degraded = False
        self._vector_size: int = 0
        self._last_check: float = 0.0
        self._backoff: float = 1.0

    # ── Public API ─────────────────────────────────────────────────────────

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.available:
            return []
        if len(texts) == 1:
            cached = self._cache.get(texts[0])
            if cached is not None:
                return [cached]
        try:
            embeddings = _embed(texts, model=self._model)
            if not embeddings:
                return []
            if self._vector_size == 0 and embeddings:
                self._vector_size = len(embeddings[0])
            for t, vec in zip(texts, embeddings, strict=False):
                self._cache.put(t, vec)
            return embeddings
        except Exception as exc:
            log.warning("Ollama embed failed: %s", exc)
            self._degraded = True
            return []

    def embed_query(self, text: str) -> list[float]:
        if not text:
            return []
        if not self.available:
            return []
        vectors = self.embed([text])
        return vectors[0] if vectors else []

    @property
    def vector_size(self) -> int:
        return self._vector_size

    @property
    def max_input_tokens(self) -> int:
        return 0

    @property
    def available(self) -> bool:
        return not self._degraded

    def check_available(self) -> bool:
        if not self._degraded:
            return True
        now = time.monotonic()
        if now - self._last_check < self._backoff:
            return False
        self._last_check = now
        try:
            result = _health()
            if result.get("status") == "ok":
                self._degraded = False
                self._backoff = 1.0
                return True
            self._backoff = min(self._backoff * 2, 60.0)
            return False
        except Exception:
            self._backoff = min(self._backoff * 2, 60.0)
            return False

    def close(self) -> None:
        pass
