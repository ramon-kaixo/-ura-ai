"""Retry, circuit breaker, and fallback logic for LLM router."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from motor.core.llm.router.utils import _build_error, _classify_error, _is_error_result

if TYPE_CHECKING:
    from motor.core.llm.circuit_breaker import CircuitBreaker

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
    retry_enabled: bool = True,
    retry_max_attempts: int = 3,
    retry_backoff_base: float = 1.0,
    retry_backoff_max: float = 30.0,
    profiler: Any = None,
    detector: Any = None,
    baseline: Any = None,
    monitor: Any = None,
    *args,
    **kwargs,
) -> Any:
    from motor.core.llm.circuit_breaker import CircuitBreakerOpenError
    from motor.core.llm.observability import metrics

    cb = _get_cb(provider_name, circuit_breakers)
    last_error: str | None = None
    attempts = 1
    max_attempts = retry_max_attempts if retry_enabled else 1
    model = kwargs.get("model")

    for attempt in range(max_attempts):
        t0 = time.monotonic()
        try:
            if monitor:
                monitor.start_operation(provider_name, task, model)
                result = cb.call(lambda: getattr(prov_obj, method)(*args, **kwargs))
                monitor.finish_operation(provider_name, task)
            else:
                if profiler:
                    profiler.start(provider_name, task, model)
                result = cb.call(lambda: getattr(prov_obj, method)(*args, **kwargs))
                if profiler:
                    profile = profiler.stop(provider_name, task)
                    if profile:
                        if detector:
                            detector.evaluate_from_profile(profile)
                        if baseline:
                            baseline.record(
                                provider_name, task,
                                wall_time_ms=profile.wall_time_ms,
                                cpu_time_ms=profile.cpu_time_ms,
                                peak_memory_bytes=profile.peak_memory_bytes,
                            )
            latency_ms = (time.monotonic() - t0) * 1000

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
            is_transient = _is_transient_error(e)
            metrics.record(provider_name, task, latency_ms, success=False, error=error_str)
            log.warning(
                "llm_call  provider=%s op=%s latency_ms=%.0f attempt=%d error=%s transient=%s",
                provider_name, task, latency_ms, attempt + 1, error_str, is_transient,
            )
            if not is_transient or attempt >= max_attempts - 1:
                return _build_error(method, error_str)
            backoff = min(retry_backoff_base * (2**attempt), retry_backoff_max)
            time.sleep(backoff)
            attempts += 1

    return _build_error(method, last_error or "unknown")


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
    result = call_with_retry(
        prov_obj, method, task, primary, registry, circuit_breakers,
        *args, **kwargs,
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
            fallback_obj, method, task, fallback_name, registry, circuit_breakers,
            *args, **kwargs,
        )
        if not _is_error_result(fallback_result):
            return fallback_result, fallback_name
        log.warning(
            "llm_fallback  primary=%s fallback=%s op=%s error=fallback_failed",
            primary, fallback_name, task,
        )
        return result, primary

    return result, primary
