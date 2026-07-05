from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("ura.observability.health")

_HEALTHY = "healthy"
_DEGRADED = "degraded"
_UNHEALTHY = "unhealthy"


@dataclass
class HealthEntry:
    status: str = _HEALTHY
    reason: str = ""
    timestamp: str = ""
    component: str = ""


class HealthRegistry:
    def __init__(self) -> None:
        self._components: dict[str, HealthEntry] = {}
        self._lock = threading.Lock()

    def register_component(self, name: str) -> None:
        with self._lock:
            if name not in self._components:
                entry = HealthEntry(component=name, status=_HEALTHY, timestamp=datetime.now(UTC).isoformat())
            self._components[name] = entry

    def set_healthy(self, component: str, reason: str = "") -> None:
        self._set_status(component, _HEALTHY, reason)

    def set_degraded(self, component: str, reason: str = "") -> None:
        self._set_status(component, _DEGRADED, reason)

    def set_unhealthy(self, component: str, reason: str = "") -> None:
        self._set_status(component, _UNHEALTHY, reason)

    def get_status(self, component: str) -> str | None:
        with self._lock:
            entry = self._components.get(component)
            return entry.status if entry else None

    def _set_status(self, component: str, status: str, reason: str = "") -> None:
        with self._lock:
            if component not in self._components:
                self._components[component] = HealthEntry(component=component)
            entry = self._components[component]
            entry.status = status
            entry.reason = reason
            entry.timestamp = datetime.now(UTC).isoformat()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            healthy = sum(1 for e in self._components.values() if e.status == _HEALTHY)
            degraded = sum(1 for e in self._components.values() if e.status == _DEGRADED)
            unhealthy = sum(1 for e in self._components.values() if e.status == _UNHEALTHY)

            if unhealthy > 0:
                global_status = _UNHEALTHY
            elif degraded > 0:
                global_status = _DEGRADED
            else:
                global_status = _HEALTHY

            return {
                "global": global_status,
                "healthy_count": healthy,
                "degraded_count": degraded,
                "unhealthy_count": unhealthy,
                "components": {
                    name: {"status": e.status, "reason": e.reason, "timestamp": e.timestamp}
                    for name, e in self._components.items()
                },
            }
