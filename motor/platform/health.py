"""Health aggregation — unified health/readiness/liveness for all subsystems.

OBS-7: Health agregado F24..F28 + estado global.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ProbeFn = Callable[[], dict[str, Any]]


class HealthAggregator:
    """Aggregates health/readiness/liveness from multiple subsystems.

    Usage:
        agg = HealthAggregator()
        agg.register("memory", memory.health)
        agg.register("fusion", fusion_health_probe)
        status = agg.health()  # all subsystems
    """

    def __init__(self) -> None:
        self._health_probes: dict[str, ProbeFn] = {}
        self._readiness_probes: dict[str, ProbeFn] = {}
        self._liveness_probes: dict[str, ProbeFn] = {}

    def register_health(self, name: str, probe: ProbeFn) -> None:
        self._health_probes[name] = probe

    def register_readiness(self, name: str, probe: ProbeFn) -> None:
        self._readiness_probes[name] = probe

    def register_liveness(self, name: str, probe: ProbeFn) -> None:
        self._liveness_probes[name] = probe

    def health(self) -> dict[str, Any]:
        """Aggregated health. Returns all subsystem health + global status."""
        subsystems = {}
        all_ok = True
        for name, probe in self._health_probes.items():
            try:
                result = probe()
                subsystems[name] = result
                if result.get("status", "ok") != "ok":
                    all_ok = False
            except Exception as e:
                subsystems[name] = {"status": "error", "error": str(e)}
                all_ok = False

        return {
            "service": "ura",
            "status": "ok" if all_ok else "degraded",
            "subsystems": subsystems,
        }

    def readiness(self) -> dict[str, Any]:
        """Aggregated readiness. All subsystems must be ready."""
        subsystems = {}
        all_ready = True
        for name, probe in self._readiness_probes.items():
            try:
                result = probe()
                subsystems[name] = result
                if not result.get("ready", False):
                    all_ready = False
            except Exception as e:
                subsystems[name] = {"ready": False, "error": str(e)}
                all_ready = False

        subsystems_health = {}
        all_ok = True
        for name, probe in self._health_probes.items():
            try:
                result = probe()
                subsystems_health[name] = result
                if result.get("status", "ok") != "ok":
                    all_ok = False
            except Exception as e:
                subsystems_health[name] = {"status": "error", "error": str(e)}
                all_ok = False

        return {
            "service": "ura",
            "status": "ok" if all_ok else "degraded",
            "ready": all_ready,
            "subsystems": {**subsystems, **subsystems_health},
        }

    def liveness(self) -> dict[str, Any]:
        """Aggregated liveness. All subsystems must be alive."""
        subsystems = {}
        all_alive = True
        for name, probe in self._liveness_probes.items():
            try:
                result = probe()
                subsystems[name] = result
                if not result.get("alive", False):
                    all_alive = False
            except Exception as e:
                subsystems[name] = {"alive": False, "error": str(e)}
                all_alive = False

        return {
            "service": "ura",
            "alive": all_alive,
            "subsystems": subsystems,
        }


_global_aggregator = HealthAggregator()


def get_health_aggregator() -> HealthAggregator:
    return _global_aggregator


def register_f24_f28_health_probes() -> None:
    """Registers health probes for F24-F28 subsystems (OB01).

    Each probe returns {"status": "ok"} by default. Subsystems with real
    health implementations can override by registering their own probe.
    """
    _global_aggregator.register_health("f24_web", lambda: {"status": "ok"})
    _global_aggregator.register_health("f25_fusion", lambda: {"status": "ok"})
    _global_aggregator.register_health("f26_memory", lambda: {"status": "ok"})
    _global_aggregator.register_health("f27_agents", lambda: {"status": "ok"})
    _global_aggregator.register_health("f28_protocol", lambda: {"status": "ok"})
    _global_aggregator.register_readiness("f28_protocol", lambda: {"ready": True})
