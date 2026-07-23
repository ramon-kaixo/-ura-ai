"""Router de proveedores LLM con resiliencia y observabilidad.

Selecciona el proveedor, aplica circuit breaker, retry y fallback.
Toda llamada queda instrumentada con métricas y logging estructurado.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from motor.core.llm.router.capability import find_providers_by_capability, select_provider_by_capability
from motor.core.llm.router.health import health_get_cached, health_remove_cache, health_store_cache
from motor.core.llm.router.providers import DEFAULT_ROUTES, resolve, resolve_name
from motor.core.llm.router.strategy import _get_cb, call_with_fallback, call_with_retry

if TYPE_CHECKING:
    from motor.core.llm.registry import ProviderRegistry

log = logging.getLogger(__name__)


class LLMRouter:
    """Enruta peticiones LLM con circuit breaker, retry y fallback."""

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        routes: dict[str, str] | None = None,
        *,
        retry_enabled: bool = True,
        retry_max_attempts: int = 3,
        retry_backoff_base: float = 1.0,
        retry_backoff_max: float = 30.0,
        fallback_enabled: bool = True,
        fallback_max_providers: int = 3,
        health_cache_ttl: float = 30.0,
        profiling_enabled: bool = False,
        hotspot_threshold_ms: float = 0.0,
        baseline_enabled: bool = False,
        monitor_enabled: bool = False,
    ) -> None:
        from motor.core.llm.registry import registry as default_registry

        self._registry = default_registry if registry is None else registry
        self._routes = {**DEFAULT_ROUTES, **(routes or {})}
        self._retry_enabled = retry_enabled
        self._retry_max_attempts = retry_max_attempts
        self._retry_backoff_base = retry_backoff_base
        self._retry_backoff_max = retry_backoff_max
        self._fallback_enabled = fallback_enabled
        self._fallback_max_providers = fallback_max_providers
        self._health_cache_ttl = health_cache_ttl
        self._profiling_enabled = profiling_enabled
        if profiling_enabled:
            from motor.core.llm.profiler import LLMProfiler

            self._profiler = LLMProfiler(enabled=True)
        else:
            self._profiler = None
        self._hotspot_threshold_ms = hotspot_threshold_ms
        if hotspot_threshold_ms > 0:
            from motor.core.llm.detector import HotspotDetector

            self._detector = HotspotDetector(threshold_ms=hotspot_threshold_ms)
        else:
            self._detector = None
        if baseline_enabled:
            from motor.core.llm.baseline import PerformanceBaseline

            self._baseline = PerformanceBaseline()
        else:
            self._baseline = None
        if monitor_enabled:
            from motor.core.llm.monitor import PerformanceMonitor

            self._monitor = PerformanceMonitor(hotspot_threshold_ms=hotspot_threshold_ms or 2000.0)
            self._profiler = None
            self._detector = None
            self._baseline = None
        else:
            self._monitor = None

        self._circuit_breakers: dict[str, Any] = {}
        self._health_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}
        self._health_lock = threading.Lock()

    @property
    def registry(self) -> ProviderRegistry:
        return self._registry

    def circuit_state(self, provider_name: str) -> str:
        cb = self._circuit_breakers.get(provider_name)
        if cb is None:
            return "no_circuit"
        return cb.state.value

    def reset_circuit(self, provider_name: str) -> None:
        cb = self._circuit_breakers.get(provider_name)
        if cb:
            cb.reset()

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        options: dict | None = None,
        *,
        provider: str | None = None,
    ) -> str:
        prov = resolve("generate", provider, self._registry, self._routes)
        primary = resolve_name("generate", provider, self._registry, self._routes)
        result, _used = call_with_fallback(
            prov,
            "generate",
            "generate",
            primary,
            self._registry,
            self._circuit_breakers,
            self._fallback_enabled,
            self._fallback_max_providers,
            prompt,
            model=model,
            options=options,
            retry_enabled=self._retry_enabled,
            retry_max_attempts=self._retry_max_attempts,
            retry_backoff_base=self._retry_backoff_base,
            retry_backoff_max=self._retry_backoff_max,
            profiler=self._profiler,
            detector=self._detector,
            baseline=self._baseline,
            monitor=self._monitor,
        )
        return result

    def embed(
        self,
        texts: list[str],
        model: str | None = None,
        *,
        provider: str | None = None,
    ) -> list[list[float]]:
        prov = resolve("embed", provider, self._registry, self._routes)
        primary = resolve_name("embed", provider, self._registry, self._routes)
        result, _used = call_with_fallback(
            prov,
            "embed",
            "embed",
            primary,
            self._registry,
            self._circuit_breakers,
            self._fallback_enabled,
            self._fallback_max_providers,
            texts,
            model=model,
            retry_enabled=self._retry_enabled,
            retry_max_attempts=self._retry_max_attempts,
            retry_backoff_base=self._retry_backoff_base,
            retry_backoff_max=self._retry_backoff_max,
            profiler=self._profiler,
            detector=self._detector,
            baseline=self._baseline,
            monitor=self._monitor,
        )
        return result

    async def embed_async(
        self,
        texts: list[str],
        model: str | None = None,
        *,
        provider: str | None = None,
    ) -> list[list[float]]:
        prov = resolve("embed", provider, self._registry, self._routes)
        return await prov.embed_async(texts, model=model)

    def invalidate_health_cache(self, provider_name: str | None = None) -> None:
        with self._health_lock:
            if provider_name:
                self._health_cache.pop(provider_name, None)
            else:
                self._health_cache.clear()

    def health(self, *, provider: str | None = None) -> dict[str, Any]:
        prov = resolve("health", provider, self._registry, self._routes)
        name = resolve_name("health", provider, self._registry, self._routes)
        from motor.core.llm.observability import metrics

        cached = health_get_cached(name, self._health_cache, self._health_lock, self._health_cache_ttl)
        if cached is not None:
            return cached

        t0 = time.monotonic()
        cb = _get_cb(name, self._circuit_breakers)
        try:
            if self._monitor:
                self._monitor.start_operation(name, "health")
                result = cb.call(prov.health)
                self._monitor.finish_operation(name, "health")
            else:
                if self._profiler:
                    self._profiler.start(name, "health")
                result = cb.call(prov.health)
                if self._profiler:
                    profile = self._profiler.stop(name, "health")
                    if profile and self._detector:
                        self._detector.evaluate_from_profile(profile)
            latency_ms = (time.monotonic() - t0) * 1000
            metrics.record(name, "health", latency_ms, success=True)
            result["latency_ms"] = latency_ms
            health_store_cache(name, result, self._health_cache, self._health_lock)
            return result
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            error_str = _classify_error(e)
            metrics.record(name, "health", latency_ms, success=False, error=error_str)
            health_remove_cache(name, self._health_cache, self._health_lock)
            return {"provider": name, "status": "error", "detail": str(e), "latency_ms": latency_ms}

    def find_providers_by_capability(self, capability: str) -> list[str]:
        return find_providers_by_capability(capability, self._registry)

    def select_provider_by_capability(
        self,
        capability: str,
        preferred: str | None = None,
    ) -> str:
        return select_provider_by_capability(capability, preferred, self._registry)

    def generate_with_capability(
        self,
        prompt: str,
        capability: str = "chat",
        model: str | None = None,
        options: dict | None = None,
    ) -> str:
        provider_name = self.select_provider_by_capability(capability)
        return self.generate(prompt, model=model, options=options, provider=provider_name)
