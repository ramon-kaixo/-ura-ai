"""Detector de hotspots (operaciones lentas) sobre el profiler LLM.

Configurable por umbral de wall time.
Thread-safe. Ranking interno de las N operaciones más lentas.
"""

from __future__ import annotations

import threading
import time
from typing import Any


class HotspotRecord:
    """Registro de una operación que superó el umbral de hotspot."""

    __slots__ = (
        "allocations_count",
        "cpu_time_ms",
        "operation",
        "peak_memory_bytes",
        "provider",
        "rank",
        "timestamp",
        "wall_time_ms",
    )

    def __init__(
        self,
        provider: str,
        operation: str,
        wall_time_ms: float,
        cpu_time_ms: float,
        peak_memory_bytes: int = 0,
        allocations_count: int = 0,
    ) -> None:
        self.provider = provider
        self.operation = operation
        self.wall_time_ms = wall_time_ms
        self.cpu_time_ms = cpu_time_ms
        self.peak_memory_bytes = peak_memory_bytes
        self.allocations_count = allocations_count
        self.timestamp = time.monotonic()
        self.rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "wall_time_ms": round(self.wall_time_ms, 1),
            "cpu_time_ms": round(self.cpu_time_ms, 1),
            "peak_memory_kb": round(self.peak_memory_bytes / 1024, 1),
            "allocations": self.allocations_count,
            "rank": self.rank,
        }

    def __repr__(self) -> str:
        return (
            f"Hotspot(rank={self.rank}, provider={self.provider!r}, "
            f"op={self.operation!r}, wall={self.wall_time_ms:.0f}ms)"
        )


class HotspotDetector:
    """Detecta operaciones lentas sobre la infraestructura de profiling.

    Uso:
        detector = HotspotDetector(threshold_ms=2000)
        detector.evaluate(profile)  # retorna True si es hotspot
        detector.get_hotspots(10)   # top 10 más lentos
    """

    def __init__(
        self,
        threshold_ms: float = 2000.0,
        max_records: int = 100,
    ) -> None:
        self._threshold_ms = threshold_ms
        self._max_records = max_records
        self._records: list[HotspotRecord] = []
        self._lock = threading.Lock()

    @property
    def threshold_ms(self) -> float:
        return self._threshold_ms

    @threshold_ms.setter
    def threshold_ms(self, value: float) -> None:
        with self._lock:
            self._threshold_ms = value

    def evaluate(
        self,
        provider: str,
        operation: str,
        wall_time_ms: float,
        cpu_time_ms: float = 0.0,
        peak_memory_bytes: int = 0,
        allocations_count: int = 0,
    ) -> HotspotRecord | None:
        """Evalúa si una operación es hotspot. Retorna HotspotRecord si supera
        el umbral, None en caso contrario."""
        if wall_time_ms < self._threshold_ms:
            return None

        record = HotspotRecord(
            provider=provider,
            operation=operation,
            wall_time_ms=wall_time_ms,
            cpu_time_ms=cpu_time_ms,
            peak_memory_bytes=peak_memory_bytes,
            allocations_count=allocations_count,
        )

        with self._lock:
            self._records.append(record)
            if len(self._records) > self._max_records:
                self._records.pop(0)
            # Recalcular rankings
            self._recalculate_rankings()

        return record

    def evaluate_from_profile(self, profile: Any) -> HotspotRecord | None:
        """Evalúa desde un objeto LLMOperationProfile."""
        if profile is None:
            return None
        return self.evaluate(
            provider=profile.provider,
            operation=profile.operation,
            wall_time_ms=profile.wall_time_ms,
            cpu_time_ms=profile.cpu_time_ms,
            peak_memory_bytes=profile.peak_memory_bytes,
            allocations_count=profile.allocations_count,
        )

    def _recalculate_rankings(self) -> None:
        """Ordena registros por wall_time descendente y asigna ranking."""
        self._records.sort(key=lambda r: r.wall_time_ms, reverse=True)
        for i, rec in enumerate(self._records):
            rec.rank = i + 1

    def get_hotspots(
        self,
        n: int = 10,
        sort_by: str = "wall_time",
    ) -> list[dict[str, Any]]:
        """Retorna los N hotspots más relevantes."""
        with self._lock:
            if not self._records:
                return []

            key_fn = {
                "wall_time": lambda r: r.wall_time_ms,
                "cpu_time": lambda r: r.cpu_time_ms,
                "memory": lambda r: r.peak_memory_bytes,
            }.get(sort_by, lambda r: r.wall_time_ms)

            sorted_recs = sorted(self._records, key=key_fn, reverse=True)
            return [r.to_dict() for r in sorted_recs[:n]]

    def get_stats(self) -> dict[str, Any]:
        """Estadísticas agregadas de hotspots detectados."""
        with self._lock:
            if not self._records:
                return {"total_hotspots": 0, "threshold_ms": self._threshold_ms}

            wall_times = [r.wall_time_ms for r in self._records]
            return {
                "total_hotspots": len(self._records),
                "threshold_ms": self._threshold_ms,
                "avg_wall_time_ms": round(sum(wall_times) / len(wall_times), 1),
                "max_wall_time_ms": round(max(wall_times), 1),
                "min_wall_time_ms": round(min(wall_times), 1),
                "providers": list({r.provider for r in self._records}),
            }

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
