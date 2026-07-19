"""Profiler interno para llamadas LLM.

Mide por operación:
  - tiempo de pared (wall time)
  - tiempo de CPU
  - memoria pico (tracemalloc)
  - número de asignaciones

Sin dependencias externas. Solo stdlib.
Integración opcional vía LLMRouter(profiling_enabled=True).
"""

from __future__ import annotations

import gc
import threading
import time
import tracemalloc
from typing import Any


class LLMOperationProfile:
    """Perfil de una operación LLM individual."""

    __slots__ = (
        "allocations_count",
        "cpu_time_ms",
        "model",
        "operation",
        "peak_memory_bytes",
        "provider",
        "timestamp",
        "wall_time_ms",
    )

    def __init__(
        self,
        provider: str,
        operation: str,
        model: str | None = None,
    ) -> None:
        self.provider = provider
        self.operation = operation
        self.model = model
        self.wall_time_ms: float = 0.0
        self.cpu_time_ms: float = 0.0
        self.peak_memory_bytes: int = 0
        self.allocations_count: int = 0
        self.timestamp: float = time.monotonic()

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "model": self.model,
            "wall_time_ms": round(self.wall_time_ms, 1),
            "cpu_time_ms": round(self.cpu_time_ms, 1),
            "peak_memory_kb": round(self.peak_memory_bytes / 1024, 1),
            "allocations": self.allocations_count,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"LLMOperationProfile(provider={self.provider!r}, "
            f"op={self.operation!r}, wall={self.wall_time_ms:.0f}ms, "
            f"cpu={self.cpu_time_ms:.0f}ms, "
            f"mem={self.peak_memory_bytes / 1024:.0f}KB)"
        )


class LLMProfiler:
    """Profiler continuo para el cliente LLM.

    Uso:
        profiler = LLMProfiler()
        profiler.start("ollama", "generate", "qwen2.5:7b")
        # ... llamada LLM ...
        profile = profiler.stop()
        print(profile.peak_memory_bytes)

    Thread-safe. Permite múltiples operaciones concurrentes
    identificadas por (provider, operation, thread_id).
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._lock = threading.Lock()
        self._snapshots: dict[str, tuple[float, float, tracemalloc.Snapshot]] = {}
        self._profiles: list[LLMOperationProfile] = []
        self._max_profiles: int = 1000

        if enabled and not tracemalloc.is_tracing():
            tracemalloc.start()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def is_tracing(self) -> bool:
        return tracemalloc.is_tracing()

    def _key(self, provider: str, operation: str) -> str:
        return f"{provider}:{operation}:{threading.get_ident()}"

    def start(self, provider: str, operation: str, model: str | None = None) -> LLMOperationProfile | None:
        """Inicia medición para una operación. Retorna None si disabled."""
        if not self._enabled:
            return None

        profile = LLMOperationProfile(provider, operation, model)
        wall_start = time.monotonic()
        cpu_start = time.process_time()
        gc.collect()
        snap = tracemalloc.take_snapshot()

        key = self._key(provider, operation)
        with self._lock:
            self._snapshots[key] = (wall_start, cpu_start, snap)
            self._profiles.append(profile)

        return profile

    def stop(self, provider: str, operation: str) -> LLMOperationProfile | None:
        """Finaliza medición. Retorna None si no hay medición activa o disabled."""
        if not self._enabled:
            return None

        key = self._key(provider, operation)
        with self._lock:
            entry = self._snapshots.pop(key, None)
            if entry is None:
                return None
            wall_start, cpu_start, start_snap = entry
            profile = self._profiles[-1]  # El último iniciado para este hilo

        wall_end = time.monotonic()
        cpu_end = time.process_time()
        gc.collect()
        end_snap = tracemalloc.take_snapshot()

        profile.wall_time_ms = (wall_end - wall_start) * 1000
        profile.cpu_time_ms = (cpu_end - cpu_start) * 1000

        # Memoria: diff between start and end snapshots
        stat_diff = end_snap.compare_to(start_snap, "lineno")
        profile.peak_memory_bytes = sum(s.size for s in stat_diff if s.size > 0)
        profile.allocations_count = sum(s.count for s in stat_diff if s.count > 0)

        return profile

    def get_recent(self, n: int = 10) -> list[dict[str, Any]]:
        """Últimos N perfiles como dicts."""
        with self._lock:
            return [p.to_dict() for p in self._profiles[-n:]]

    def get_stats(self, provider: str | None = None) -> dict[str, Any]:
        """Estadísticas agregadas por proveedor."""
        with self._lock:
            filtered = [p for p in self._profiles if p.provider == provider] if provider else self._profiles
            if not filtered:
                return {}

            total_wall = sum(p.wall_time_ms for p in filtered)
            total_cpu = sum(p.cpu_time_ms for p in filtered)
            peak_mem = max(p.peak_memory_bytes for p in filtered)
            total_alloc = sum(p.allocations_count for p in filtered)

            return {
                "total_operations": len(filtered),
                "total_wall_time_ms": round(total_wall, 1),
                "total_cpu_time_ms": round(total_cpu, 1),
                "avg_wall_time_ms": round(total_wall / len(filtered), 1),
                "avg_cpu_time_ms": round(total_cpu / len(filtered), 1),
                "peak_memory_kb": round(peak_mem / 1024, 1),
                "total_allocations": total_alloc,
            }

    def reset(self) -> None:
        with self._lock:
            self._snapshots.clear()
            self._profiles.clear()
            if tracemalloc.is_tracing():
                tracemalloc.stop()
                tracemalloc.start()

    def close(self) -> None:
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        self._snapshots.clear()
        self._profiles.clear()
        self._enabled = False


# Singleton por defecto (desactivado hasta que se active explícitamente)
profiler = LLMProfiler(enabled=False)
