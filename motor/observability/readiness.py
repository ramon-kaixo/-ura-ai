from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("ura.observability.readiness")


@dataclass
class ReadinessEntry:
    ready: bool = False
    reason: str = ""
    dependency: str = ""


class ReadinessRegistry:
    def __init__(self) -> None:
        self._dependencies: dict[str, ReadinessEntry] = {}
        self._lock = threading.Lock()

    def register_dependency(self, name: str) -> None:
        with self._lock:
            if name not in self._dependencies:
                self._dependencies[name] = ReadinessEntry(dependency=name)

    def set_ready(self, dependency: str) -> None:
        with self._lock:
            if dependency in self._dependencies:
                self._dependencies[dependency].ready = True
                self._dependencies[dependency].reason = ""

    def set_not_ready(self, dependency: str, reason: str = "") -> None:
        with self._lock:
            if dependency in self._dependencies:
                self._dependencies[dependency].ready = False
                self._dependencies[dependency].reason = reason

    def is_ready(self) -> bool:
        with self._lock:
            return all(d.ready for d in self._dependencies.values()) if self._dependencies else True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            ready = all(d.ready for d in self._dependencies.values()) if self._dependencies else True
            return {
                "ready": ready,
                "dependencies": {
                    name: {"ready": e.ready, "reason": e.reason} for name, e in self._dependencies.items()
                },
            }
