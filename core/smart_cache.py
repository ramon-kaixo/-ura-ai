#!/usr/bin/env python3
"""
Caché inteligente para respuestas de URA.
Usa un dict en memoria con TTL y permite invalidación selectiva.
"""

import time
import threading
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SmartCache:
    def __init__(self, default_ttl: int = 300):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl  # segundos por defecto

    def get(self, key: str) -> Any | None:
        """Obtiene un valor si no ha expirado."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            timestamp, value = entry
            if time.time() - timestamp > self._default_ttl:
                del self._cache[key]
                return None
            logger.debug(f"Cache HIT: {key[:60]}...")
            return value

    def set(self, key: str, value: Any, ttl: int | None = None):
        """Guarda un valor con TTL (usa el default si no se especifica)."""
        with self._lock:
            self._cache[key] = (time.time(), value)
            logger.debug(f"Cache SET: {key[:60]}...")

    def invalidate(self, pattern: str):
        """Elimina todas las claves que contienen el patrón."""
        with self._lock:
            before = len(self._cache)
            self._cache = {k: v for k, v in self._cache.items() if pattern not in k}
            removed = before - len(self._cache)
            if removed:
                logger.info(
                    f"Cache invalidado por patrón '{pattern}': {removed} entradas eliminadas."
                )

    def clear(self):
        """Limpia todo el caché."""
        with self._lock:
            self._cache.clear()
            logger.info("Cache completamente limpiado.")


# Singleton
_smart_cache: SmartCache | None = None


def get_smart_cache(default_ttl: int = 300) -> SmartCache:
    global _smart_cache
    if _smart_cache is None:
        _smart_cache = SmartCache(default_ttl=default_ttl)
    return _smart_cache
