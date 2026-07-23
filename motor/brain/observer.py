"""Observador proactivo del cerebro.

Lee health checks de todos los subsistemas y detecta anomalias.
NO reinventa metricas — usa los health() que ya existen.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("ura.brain.observer")


@dataclass
class HealthObservation:
    timestamp: float
    subsystem: str
    status: str
    raw_data: dict[str, Any]
    anomaly: str | None = None


class BrainObserver:
    """Observa todos los subsistemas y detecta degradacion."""

    def __init__(self) -> None:
        self._history: dict[str, list[HealthObservation]] = {}
        self._providers: list[tuple[str, Callable[[], dict[str, Any]]]] = []

    def register_provider(self, name: str, health_fn: Callable[[], dict[str, Any]]) -> None:
        self._providers.append((name, health_fn))

    def observe_all(self) -> list[HealthObservation]:
        observations: list[HealthObservation] = []
        for name, health_fn in self._providers:
            try:
                raw = health_fn()
                obs = self._analyze(name, raw)
                observations.append(obs)
                self._record(name, obs)
            except Exception as e:
                obs = HealthObservation(
                    timestamp=time.time(),
                    subsystem=name,
                    status="error",
                    raw_data={"error": str(e)},
                    anomaly=f"Health check failed: {e}",
                )
                observations.append(obs)
        return observations

    def _analyze(self, name: str, raw: dict[str, Any]) -> HealthObservation:
        status = raw.get("status", "unknown")
        latency = raw.get("latency_ms", 0)
        anomaly: str | None = None
        if status == "error":
            anomaly = f"Provider {name} reports error"
        elif latency > 1000:
            anomaly = f"Latency critical: {latency:.0f}ms"
        elif latency > 500:
            status = "warning"
            anomaly = f"Latency elevated: {latency:.0f}ms"
        return HealthObservation(
            timestamp=time.time(),
            subsystem=name,
            status=status,
            raw_data=raw,
            anomaly=anomaly,
        )

    def _record(self, name: str, obs: HealthObservation) -> None:
        if name not in self._history:
            self._history[name] = []
        self._history[name].append(obs)
        self._history[name] = self._history[name][-100:]

    def get_history(self, name: str, limit: int = 10) -> list[HealthObservation]:
        return self._history.get(name, [])[-limit:]

    def get_critical(self) -> list[HealthObservation]:
        critical: list[HealthObservation] = []
        for history in self._history.values():
            for obs in history:
                if obs.status in ("error", "critical") or obs.anomaly:
                    critical.append(obs)
        return critical
