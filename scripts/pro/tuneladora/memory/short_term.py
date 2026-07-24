"""Fase 2: ShortTermMemory — memória temporal en proceso."""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("tuneladora.memory.short_term")


@dataclass(frozen=True)
class STMEntry:
    key: str
    value: Any
    ttl: float
    timestamp: float = field(default_factory=time.time)

    def expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


class ShortTermMemory:
    def __init__(self, max_size: int = 500, default_ttl: float = 300.0) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, STMEntry] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            self._evict_expired()
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expired():
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            self._evict_expired()
            entry = STMEntry(key=key, value=value, ttl=ttl or self._default_ttl)
            self._store[key] = entry
            self._store.move_to_end(key)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)
            log.debug("STM set %s", key)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def has(self, key: str) -> bool:
        with self._lock:
            self._evict_expired()
            return key in self._store

    def keys(self) -> list[str]:
        with self._lock:
            self._evict_expired()
            return list(self._store.keys())

    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v.timestamp > v.ttl]
        for k in expired:
            del self._store[k]
