"""OllamaEmbedder — implementa Embedder(Protocol) vía API de Ollama.

Dependencia: httpx (ya disponible).
Cache LRU in-process con TTL configurable.
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from typing import Any

import httpx

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
    """Embedder usando API de embeddings de Ollama.

    Args:
        model: Nombre del modelo en Ollama.
        base_url: URL base del servidor Ollama.
        cache_ttl: TTL del cache LRU en segundos.
        timeout: Timeout para requests HTTP.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        cache_ttl: int = 300,
        timeout: float = 30.0,
    ):
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)
        self._cache = _LRUCache(ttl=cache_ttl)
        self._degraded = False
        self._vector_size: int = 0
        self._max_tokens: int = 0
        self._last_check: float = 0.0
        self._backoff: float = 1.0

    # ── Public API ─────────────────────────────────────────────────────────

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.available:
            return []
        # Cache lookup for single texts
        if len(texts) == 1:
            cached = self._cache.get(texts[0])
            if cached is not None:
                return [cached]
        try:
            resp = self._client.post(
                "/api/embed",
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings: list[list[float]] = data.get("embeddings", [])
            if not embeddings:
                return []
            # Auto-detect vector size
            if self._vector_size == 0 and embeddings:
                self._vector_size = len(embeddings[0])
            # Cache individual texts
            for t, vec in zip(texts, embeddings, strict=False):
                self._cache.put(t, vec)
            return embeddings
        except httpx.HTTPError as exc:
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
        if self._max_tokens == 0:
            self._load_model_info()
        return self._max_tokens

    @property
    def available(self) -> bool:
        """O(1), sin side-effects. Refleja último estado conocido."""
        return not self._degraded

    def check_available(self) -> bool:
        """Verifica disponibilidad en tiempo real con exponential backoff.

        Side-effects: muta _degraded y _backoff.
        """
        if not self._degraded:
            return True
        now = time.monotonic()
        if now - self._last_check < self._backoff:
            return False
        self._last_check = now
        try:
            resp = self._client.get("/api/tags")
            if resp.status_code == 200:
                self._degraded = False
                self._backoff = 1.0
                return True
            self._backoff = min(self._backoff * 2, 60.0)
            return False
        except httpx.HTTPError:
            self._backoff = min(self._backoff * 2, 60.0)
            return False

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def close(self) -> None:
        """Cierra el cliente HTTP. Llamar al finalizar."""
        self._client.close()

    def _load_model_info(self) -> dict[str, Any]:
        """Carga información del modelo desde /api/show."""
        try:
            resp = self._client.post(
                "/api/show",
                json={"model": self._model},
            )
            resp.raise_for_status()
            data = resp.json()
            modelfile = data.get("modelfile", "")
            for line in modelfile.splitlines():
                if line.startswith("PARAMETER"):
                    parts = line.split()
                    if len(parts) >= 3 and parts[1] == "num_ctx":
                        self._max_tokens = int(parts[2])
                        break
            return data
        except httpx.HTTPError:
            log.debug("Could not load model info for %s", self._model)
            return {}
        except (json.JSONDecodeError, KeyError, ValueError, IndexError):
            log.debug("Could not parse model info for %s", self._model)
            return {}
