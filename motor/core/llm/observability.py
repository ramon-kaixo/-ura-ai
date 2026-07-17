"""Observabilidad — métricas por proveedor LLM.

Almacena métricas en memoria. Thread-safe.
Se puede extender para exportar a Prometheus en el futuro.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

from motor.core.llm._logging import percentile


class LLMMetrics:
    """Métricas por proveedor/operación. Thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._errors: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._tokens: dict[str, list[float]] = defaultdict(list)
        self._total_calls: dict[str, int] = defaultdict(int)
        self._success_calls: dict[str, int] = defaultdict(int)
        self._fail_calls: dict[str, int] = defaultdict(int)
        self._start_time = time.monotonic()

    def record(
        self,
        provider: str,
        operation: str,
        latency_ms: float,
        *,
        success: bool,
        error: str | None = None,
        tokens: int | None = None,
    ) -> None:
        with self._lock:
            key = (provider, operation)
            self._calls[key].append(latency_ms)
            self._total_calls[provider] += 1
            if success:
                self._success_calls[provider] += 1
            else:
                self._fail_calls[provider] += 1
                if error:
                    self._errors[key][error] += 1
            if tokens is not None:
                self._tokens[provider].append(float(tokens))

    def get_stats(self, provider: str | None = None, operation: str | None = None) -> dict[str, Any]:
        """Estadísticas agregadas. Filtra por provider y/u operation."""
        with self._lock:
            result: dict[str, Any] = {}
            elapsed = max(1.0, time.monotonic() - self._start_time)

            for (prov, op), latencias in self._calls.items():
                if provider and prov != provider:
                    continue
                if operation and op != operation:
                    continue
                key = f"{prov}.{op}"
                result[key] = {
                    "provider": prov,
                    "operation": op,
                    "llamadas_totales": len(latencias),
                    "latencia_p50_ms": percentile(latencias, 50),
                    "latencia_p95_ms": percentile(latencias, 95),
                    "latencia_p99_ms": percentile(latencias, 99),
                    "latencia_min_ms": min(latencias),
                    "latencia_max_ms": max(latencias),
                    "latencia_media_ms": sum(latencias) / len(latencias) if latencias else 0.0,
                }

                # Errores
                errs = self._errors.get((prov, op), {})
                result[key]["errores"] = dict(errs)

                # Throughput
                total = self._total_calls.get(prov, 0)
                result[key]["throughput_qps"] = total / elapsed

                # Tokens
                toks = self._tokens.get(prov, [])
                if toks:
                    result[key]["tokens_por_segundo"] = sum(toks) / elapsed
                    result[key]["tokens_medios_por_call"] = sum(toks) / len(toks)

            if not result:
                return {"error": "no data"}
            return result

    def summary(self) -> dict[str, Any]:
        """Resumen rápido por proveedor."""
        with self._lock:
            result: dict[str, Any] = {}
            all_provs = set(self._total_calls) | set(self._success_calls) | set(self._fail_calls)
            for prov in all_provs:
                total = self._total_calls.get(prov, 0)
                ok = self._success_calls.get(prov, 0)
                fail = self._fail_calls.get(prov, 0)
                result[prov] = {
                    "total": total,
                    "ok": ok,
                    "fail": fail,
                }
            return result

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()
            self._errors.clear()
            self._tokens.clear()
            self._total_calls.clear()
            self._success_calls.clear()
            self._fail_calls.clear()
            self._start_time = time.monotonic()


# Singleton global
metrics = LLMMetrics()
