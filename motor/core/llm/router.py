"""Router de proveedores LLM con resiliencia y observabilidad.

Selecciona el proveedor, aplica circuit breaker, retry y fallback.
Toda llamada queda instrumentada con métricas y logging estructurado.
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.core.llm.registry import ProviderRegistry

log = logging.getLogger(__name__)

DEFAULT_ROUTES: dict[str, str] = {
    "generate": "ollama",
    "embed": "ollama",
    "health": "ollama",
}

_ERROR_STR_EXCEEDED = "Error: La generación excedió el tiempo de espera."
_ERROR_STR_CONNECTION = "Error: No se pudo conectar con el servicio de generación."


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

            self._monitor = PerformanceMonitor(
                hotspot_threshold_ms=hotspot_threshold_ms or 2000.0,
            )
            # El monitor reemplaza los componentes individuales
            self._profiler = None
            self._detector = None
            self._baseline = None
        else:
            self._monitor = None

        # Circuit breakers por proveedor (inicialización perezosa)
        self._circuit_breakers: dict[str, Any] = {}

        # Caché de health (thread-safe)
        self._health_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}
        self._health_lock = threading.Lock()

    @property
    def registry(self) -> ProviderRegistry:
        return self._registry

    # ── Circuit breaker ──────────────────────────────────────

    def _get_cb(self, provider_name: str) -> Any:
        if provider_name not in self._circuit_breakers:
            from motor.core.llm.circuit_breaker import CircuitBreaker

            self._circuit_breakers[provider_name] = CircuitBreaker(provider_name)
        return self._circuit_breakers[provider_name]

    def circuit_state(self, provider_name: str) -> str:
        cb = self._circuit_breakers.get(provider_name)
        if cb is None:
            return "no_circuit"
        return cb.state.value

    def reset_circuit(self, provider_name: str) -> None:
        cb = self._circuit_breakers.get(provider_name)
        if cb:
            cb.reset()

    # ── Resolución de proveedor ──────────────────────────────

    def _resolve(self, task: str, provider: str | None) -> Any:
        if provider:
            if provider not in self._registry:
                raise RuntimeError(
                    f"Provider '{provider}' not in registry for task "
                    f"'{task}'. Available: {list(self._registry.list())}"
                )
            return self._registry.get(provider)
        name = self._routes.get(task) or self._registry.default_name
        if name is None:
            raise RuntimeError(
                f"No provider available for task '{task}'. "
                "Register a provider first via registry.register()."
            )
        if name not in self._registry:
            name = self._registry.default_name
        if name is None:
            raise RuntimeError(
                f"No provider available for task '{task}'. "
                "Route resolved to an unregistered provider "
                f"and no fallback default is set. "
                f"Available: {list(self._registry.list())}"
            )
        return self._registry.get(name)

    def _list_available(self, exclude: str | None = None) -> list[str]:
        return [n for n in self._registry.list() if n != exclude]

    # ── Retry + CB ──────────────────────────────────────────

    def _call_with_retry(self, prov_obj: Any, method: str, task: str, provider_name: str, *args, **kwargs) -> Any:  # noqa: C901
        from motor.core.llm.circuit_breaker import CircuitBreakerOpenError
        from motor.core.llm.observability import metrics

        cb = self._get_cb(provider_name)
        last_error: str | None = None
        attempts = 1
        max_attempts = self._retry_max_attempts if self._retry_enabled else 1
        model = kwargs.get("model")

        for attempt in range(max_attempts):
            t0 = time.monotonic()
            try:
                if self._monitor:
                    self._monitor.start_operation(provider_name, task, model)
                    result = cb.call(lambda: getattr(prov_obj, method)(*args, **kwargs))
                    self._monitor.finish_operation(provider_name, task)
                else:
                    if self._profiler:
                        self._profiler.start(provider_name, task, model)
                    result = cb.call(lambda: getattr(prov_obj, method)(*args, **kwargs))
                    if self._profiler:
                        profile = self._profiler.stop(provider_name, task)
                        if profile:
                            if self._detector:
                                self._detector.evaluate_from_profile(profile)
                            if self._baseline:
                                self._baseline.record(
                                    provider_name, task,
                                    wall_time_ms=profile.wall_time_ms,
                                    cpu_time_ms=profile.cpu_time_ms,
                                    peak_memory_bytes=profile.peak_memory_bytes,
                                )
                latency_ms = (time.monotonic() - t0) * 1000

                tokens = None
                tokens = None
                if method == "generate" and isinstance(result, str):
                    tokens = max(1, len(result) // 4)

                metrics.record(provider_name, task, latency_ms, success=True, tokens=tokens)
                log.info(
                    "llm_call  provider=%s op=%s latency_ms=%.0f attempt=%d cb=%s",
                    provider_name, task, latency_ms, attempt + 1, cb.state.value,
                )
                return result

            except CircuitBreakerOpenError as e:
                latency_ms = (time.monotonic() - t0) * 1000
                metrics.record(provider_name, task, latency_ms, success=False, error="circuit_open")
                log.warning(
                    "llm_call  provider=%s op=%s latency_ms=%.0f error=circuit_open retry_after=%.0fs",
                    provider_name, task, latency_ms, e.retry_after,
                )
                return _build_error(method, "circuit_breaker_open")

            except Exception as e:
                latency_ms = (time.monotonic() - t0) * 1000
                error_str = _classify_error(e)
                last_error = error_str
                is_transient = self._is_transient_error(e)
                metrics.record(provider_name, task, latency_ms, success=False, error=error_str)
                log.warning(
                    "llm_call  provider=%s op=%s latency_ms=%.0f attempt=%d error=%s transient=%s",
                    provider_name, task, latency_ms, attempt + 1, error_str, is_transient,
                )

                if not is_transient or attempt >= max_attempts - 1:
                    return _build_error(method, error_str)

                # Backoff exponencial
                backoff = min(
                    self._retry_backoff_base * (2 ** attempt),
                    self._retry_backoff_max,
                )
                time.sleep(backoff)
                attempts += 1

        return _build_error(method, last_error or "unknown")

    def _is_transient_error(self, exception: Exception) -> bool:
        if isinstance(exception, (TimeoutError, ConnectionError)):
            return True
        try:
            import httpx
        except ImportError:
            return False
        if isinstance(exception, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
            return True
        if isinstance(exception, httpx.HTTPStatusError):
            return exception.response.status_code in (429, 500, 502, 503, 504)
        return False

    # ── Fallback ────────────────────────────────────────────

    def _call_with_fallback(
        self, prov_obj: Any, method: str, task: str, primary: str, *args, **kwargs,
    ) -> tuple[Any, str | None]:
        result = self._call_with_retry(prov_obj, method, task, primary, *args, **kwargs)
        if not _is_error_result(result) or not self._fallback_enabled:
            return result, primary

        available = self._list_available(exclude=primary)
        if not available:
            return result, primary

        # Buscar el primer proveedor alternativo disponible (CB no OPEN),
        # limitado a fallback_max_providers. Sin cadena: solo se intenta 1.
        for fallback_name in available[: self._fallback_max_providers]:
            cb = self._get_cb(fallback_name)
            if not cb.is_available:
                continue

            fallback_obj = self._registry.get(fallback_name)
            log.info("llm_fallback  primary=%s fallback=%s op=%s", primary, fallback_name, task)
            fallback_result = self._call_with_retry(fallback_obj, method, task, fallback_name, *args, **kwargs)
            if not _is_error_result(fallback_result):
                return fallback_result, fallback_name
            # Fallback falló — no encadenar, retornar error del primario
            log.warning(
                "llm_fallback  primary=%s fallback=%s op=%s error=fallback_failed",
                primary, fallback_name, task,
            )
            return result, primary

        return result, primary

    # ── API pública ─────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        options: dict | None = None,
        *,
        provider: str | None = None,
    ) -> str:
        prov = self._resolve("generate", provider)
        primary = self._resolve_name("generate", provider)
        result, _used = self._call_with_fallback(
            prov, "generate", "generate", primary, prompt, model=model, options=options,
        )
        return result

    def embed(
        self,
        texts: list[str],
        model: str | None = None,
        *,
        provider: str | None = None,
    ) -> list[list[float]]:
        prov = self._resolve("embed", provider)
        primary = self._resolve_name("embed", provider)
        result, _used = self._call_with_fallback(
            prov, "embed", "embed", primary, texts, model=model,
        )
        return result

    async def embed_async(
        self,
        texts: list[str],
        model: str | None = None,
        *,
        provider: str | None = None,
    ) -> list[list[float]]:
        prov = self._resolve("embed", provider)
        return await prov.embed_async(texts, model=model)

    def invalidate_health_cache(self, provider_name: str | None = None) -> None:
        """Invalida la caché de salud. Si provider_name es None, invalida todo."""
        with self._health_lock:
            if provider_name:
                self._health_cache.pop(provider_name, None)
            else:
                self._health_cache.clear()

    def _health_get_cached(self, name: str) -> dict[str, Any] | None:
        """Retorna entrada de caché válida o None. Thread-safe."""
        self._health_lock.acquire()
        try:
            entry = self._health_cache.get(name)
            if entry is not None:
                cached_at, cached_result = entry
                if cached_result is not None and time.monotonic() - cached_at < self._health_cache_ttl:
                    return cached_result
                if cached_result is None:
                    # Otra llamada en curso — esperar con backoff
                    for _ in range(20):
                        self._health_lock.release()
                        time.sleep(0.005)
                        self._health_lock.acquire()
                        entry2 = self._health_cache.get(name)
                        if entry2 is not None and entry2[1] is not None:
                            return entry2[1]
                    # Timeout — continuar, la otra llamada probablemente falló
            # Marcar "en curso"
            self._health_cache[name] = (0.0, None)
            return None
        finally:
            with suppress(RuntimeError):
                self._health_lock.release()

    def _health_store_cache(self, name: str, result: dict[str, Any]) -> None:
        with self._health_lock:
            self._health_cache[name] = (time.monotonic(), result)

    def _health_remove_cache(self, name: str) -> None:
        with self._health_lock:
            self._health_cache.pop(name, None)

    def health(self, *, provider: str | None = None) -> dict[str, Any]:
        prov = self._resolve("health", provider)
        name = self._resolve_name("health", provider)
        from motor.core.llm.observability import metrics

        cached = self._health_get_cached(name)
        if cached is not None:
            return cached

        t0 = time.monotonic()
        cb = self._get_cb(name)
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
            self._health_store_cache(name, result)
            return result
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            error_str = _classify_error(e)
            metrics.record(name, "health", latency_ms, success=False, error=error_str)
            self._health_remove_cache(name)
            return {"provider": name, "status": "error", "detail": str(e), "latency_ms": latency_ms}

    # ── Internos ────────────────────────────────────────────

    def _resolve_name(self, task: str, provider: str | None) -> str:
        if provider:
            return provider
        name = self._routes.get(task) or self._registry.default_name
        if name and name not in self._registry:
            name = self._registry.default_name
        return name or "unknown"


# ── Funciones auxiliares ──────────────────────────────────

def _classify_error(exception: Exception) -> str:
    try:
        import httpx
    except ImportError:
        return "error"
    if isinstance(exception, httpx.TimeoutException):
        return "timeout"
    if isinstance(exception, httpx.ConnectError):
        return "connection_error"
    if isinstance(exception, httpx.RemoteProtocolError):
        return "protocol_error"
    if isinstance(exception, httpx.HTTPStatusError):
        return f"http_{exception.response.status_code}"
    return f"unexpected:{type(exception).__name__}"


def _is_error_result(result: Any) -> bool:
    return isinstance(result, str) and result.startswith("Error:")


def _build_error(method: str, error: str) -> Any:
    if method in ("embed", "embed_async"):
        return [[0.0] * 768]
    return f"Error: {error}"
