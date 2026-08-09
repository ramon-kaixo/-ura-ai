"""Retry, circuit breaker, and fallback logic for LLM router."""

from __future__ import annotations

import logging
import time
from typing import Any

from motor.core.llm.router.utils import _build_error, _classify_error, _is_error_result

log = logging.getLogger(__name__)


def _get_cb(provider_name: str, circuit_breakers: dict[str, Any]) -> Any:
    if provider_name not in circuit_breakers:
        from motor.core.llm.circuit_breaker import CircuitBreaker

        circuit_breakers[provider_name] = CircuitBreaker(provider_name)
    return circuit_breakers[provider_name]


def _is_transient_error(exception: Exception) -> bool:
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


def call_with_retry(
    prov_obj: Any,
    method: str,
    task: str,
    provider_name: str,
    registry: Any,
    circuit_breakers: dict[str, Any],
    prompt: str = "",
    *,
    retry_enabled: bool = True,
    retry_max_attempts: int = 3,
    retry_backoff_base: float = 1.0,
    retry_backoff_max: float = 30.0,
    profiler: Any = None,
    detector: Any = None,
    baseline: Any = None,
    monitor: Any = None,
    **kwargs,
) -> Any:
    from motor.core.llm.circuit_breaker import CircuitBreakerOpenError

    cb = _get_cb(provider_name, circuit_breakers)
    last_error: str | None = None
    attempts = 1
    max_attempts = retry_max_attempts if retry_enabled else 1
    model = kwargs.get("model")

    for attempt in range(max_attempts):
        t0 = time.monotonic()
        try:
            result = _call_provider(
                prov_obj,
                method,
                prompt,
                kwargs,
                monitor,
                profiler,
                detector,
                baseline,
                provider_name,
                task,
                model,
                cb,
            )
            return _record_success(result, method, provider_name, task, t0, attempt, cb)

        except CircuitBreakerOpenError as e:
            return _record_circuit_open(method, provider_name, task, t0, e)

        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            error_str = _classify_error(e)
            last_error = error_str
            is_transient = _is_transient_error(e)
            _record_failure(provider_name, task, latency_ms, attempt, error_str, is_transient)
            if not is_transient or attempt >= max_attempts - 1:
                return _build_error(method, error_str)
            backoff = min(retry_backoff_base * (2**attempt), retry_backoff_max)
            time.sleep(backoff)
            attempts += 1

    return _build_error(method, last_error or "unknown")


def _call_provider(
    prov_obj: Any,
    method: str,
    prompt: str,
    kwargs: dict[str, Any],
    monitor: Any,
    profiler: Any,
    detector: Any,
    baseline: Any,
    provider_name: str,
    task: str,
    model: Any,
    cb: Any,
) -> Any:
    if monitor:
        monitor.start_operation(provider_name, task, model)
        result = cb.call(lambda: getattr(prov_obj, method)(prompt, **kwargs))
        monitor.finish_operation(provider_name, task)
        return result
    if profiler:
        profiler.start(provider_name, task, model)
    result = cb.call(lambda: getattr(prov_obj, method)(prompt, **kwargs))
    if profiler:
        profile = profiler.stop(provider_name, task)
        if profile:
            if detector:
                detector.evaluate_from_profile(profile)
            if baseline:
                baseline.record(
                    provider_name,
                    task,
                    wall_time_ms=profile.wall_time_ms,
                    cpu_time_ms=profile.cpu_time_ms,
                    peak_memory_bytes=profile.peak_memory_bytes,
                )
    return result


def _record_success(
    result: Any,
    method: str,
    provider_name: str,
    task: str,
    t0: float,
    attempt: int,
    cb: Any,
) -> Any:
    from motor.core.llm.observability import metrics

    latency_ms = (time.monotonic() - t0) * 1000
    tokens = None
    if method == "generate" and isinstance(result, str):
        tokens = max(1, len(result) // 4)
    metrics.record(provider_name, task, latency_ms, success=True, tokens=tokens)
    log.info(
        "llm_call  provider=%s op=%s latency_ms=%.0f attempt=%d cb=%s",
        provider_name,
        task,
        latency_ms,
        attempt + 1,
        cb.state.value,
    )
    return result


def _record_circuit_open(
    method: str,
    provider_name: str,
    task: str,
    t0: float,
    e: Exception,
) -> Any:
    from motor.core.llm.observability import metrics

    latency_ms = (time.monotonic() - t0) * 1000
    metrics.record(provider_name, task, latency_ms, success=False, error="circuit_open")
    log.warning(
        "llm_call  provider=%s op=%s latency_ms=%.0f error=circuit_open retry_after=%.0fs",
        provider_name,
        task,
        latency_ms,
        getattr(e, "retry_after", 0.0),
    )
    return _build_error(method, "circuit_breaker_open")


def _record_failure(
    provider_name: str,
    task: str,
    latency_ms: float,
    attempt: int,
    error_str: str,
    is_transient: bool,
) -> None:
    from motor.core.llm.observability import metrics

    metrics.record(provider_name, task, latency_ms, success=False, error=error_str)
    log.warning(
        "llm_call  provider=%s op=%s latency_ms=%.0f attempt=%d error=%s transient=%s",
        provider_name,
        task,
        latency_ms,
        attempt + 1,
        error_str,
        is_transient,
    )


_RETRY_KWARGS = {
    "retry_enabled",
    "retry_max_attempts",
    "retry_backoff_base",
    "retry_backoff_max",
    "profiler",
    "detector",
    "baseline",
    "monitor",
}


def call_with_fallback(
    prov_obj: Any,
    method: str,
    task: str,
    primary: str,
    registry: Any,
    circuit_breakers: dict[str, Any],
    fallback_enabled: bool = True,
    fallback_max_providers: int = 3,
    *args,
    **kwargs,
) -> tuple[Any, str | None]:
    retry_kw = {k: kwargs.pop(k) for k in _RETRY_KWARGS if k in kwargs}
    prompt_arg: str = args[0] if args else ""
    result = call_with_retry(
        prov_obj,
        method,
        task,
        primary,
        registry,
        circuit_breakers,
        prompt=prompt_arg,
        **retry_kw,
    )
    if not _is_error_result(result) or not fallback_enabled:
        return result, primary

    available = [n for n in registry.list() if n != primary]
    if not available:
        return result, primary

    for fallback_name in available[:fallback_max_providers]:
        cb = _get_cb(fallback_name, circuit_breakers)
        if not cb.is_available:
            continue

        fallback_obj = registry.get(fallback_name)
        log.info("llm_fallback  primary=%s fallback=%s op=%s", primary, fallback_name, task)
        fallback_result = call_with_retry(
            fallback_obj,
            method,
            task,
            fallback_name,
            registry,
            circuit_breakers,
            prompt=prompt_arg,
            **retry_kw,
        )
        if not _is_error_result(fallback_result):
            return fallback_result, fallback_name
        log.warning(
            "llm_fallback  primary=%s fallback=%s op=%s error=fallback_failed",
            primary,
            fallback_name,
            task,
        )
        # ADR-007 (2026-08-09, TASK-20260809-007): el return NO debe estar
        # dentro del bucle — abortaba la cadena tras el primer fallback fallido
        # ignorando fallback_max_providers>1. Ahora se sigue al siguiente
        # proveedor disponible; si todos fallan, se devuelve el error primario.

    return result, primary
