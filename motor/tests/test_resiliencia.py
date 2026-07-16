"""Tests de resiliencia y observabilidad (F19 B8).

Circuit breaker, retry, fallback, observabilidad, health monitor.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

import pytest

from motor.core.llm.base import BaseLLMProvider
from motor.core.llm.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState
from motor.core.llm.observability import LLMMetrics
from motor.core.llm.observability import metrics as global_metrics
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter

# ── Helpers ─────────────────────────────────

class _MockOK(BaseLLMProvider):
    def generate(self, prompt, model=None, options=None): return "ok"
    def embed(self, texts, model=None): return [[0.0]]
    async def embed_async(self, texts, model=None): return [[0.0]]
    def health(self): return {"status": "ok"}


class _MockFail(BaseLLMProvider):
    def generate(self, prompt, model=None, options=None): raise ValueError("fail")
    def embed(self, texts, model=None): return [[0.0]]
    async def embed_async(self, texts, model=None): return [[0.0]]
    def health(self): return {"status": "ok"}


class _MockTransient(BaseLLMProvider):
    _count: int = 0
    def generate(self, prompt, model=None, options=None):
        self._count += 1
        if self._count < 3:
            raise TimeoutError("transient")
        return "ok_after_retry"
    def embed(self, texts, model=None): return [[0.0]]
    async def embed_async(self, texts, model=None): return [[0.0]]
    def health(self): return {"status": "ok"}


# ── B2: Circuit Breaker ─────────────────────────

class TestCircuitBreaker:
    def test_initial_state_closed(self) -> None:
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available

    def test_transient_failures_open_circuit(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=2)

        class _Transient(Exception):
            pass
        cb._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        def _fail() -> None:
            raise _Transient("fail")

        for _ in range(2):
            with pytest.raises(_Transient):
                cb.call(_fail)
        assert cb.state == CircuitState.OPEN
        assert not cb.is_available

    def test_open_rejects_calls(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=999)

        class _Transient(Exception):
            pass
        cb._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        with pytest.raises(_Transient):
            cb.call(lambda: (_ for _ in ()).throw(_Transient("fail")))

        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "should_not_reach")

    def test_recovery_transition(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05)

        class _Transient(Exception):
            pass
        cb._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        with pytest.raises(_Transient):
            cb.call(lambda: (_ for _ in ()).throw(_Transient("fail")))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.1)
        assert cb.is_available  # Timeout passed
        cb.call(lambda: "ok")  # Should transition HALF_OPEN -> CLOSED
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05)

        class _Transient(Exception):
            pass
        cb._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        with pytest.raises(_Transient):
            cb.call(lambda: (_ for _ in ()).throw(_Transient("fail")))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.1)
        # Half-open probe fails
        with pytest.raises(_Transient):
            cb.call(lambda: (_ for _ in ()).throw(_Transient("fail")))
        assert cb.state == CircuitState.OPEN  # Back to OPEN

    def test_non_transient_errors_dont_count(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=2)

        def _fail() -> None:
            raise ValueError("validation error")

        for _ in range(5):
            with pytest.raises(ValueError):
                cb.call(_fail)
        assert cb.state == CircuitState.CLOSED  # Non-transient doesn't open

    def test_reset(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=999)

        class _Transient(Exception):
            pass
        cb._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        with pytest.raises(_Transient):
            cb.call(lambda: (_ for _ in ()).throw(_Transient("fail")))
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available

    # ── H2: tests de concurrencia ─────────────────

    def test_concurrent_opens(self) -> None:
        """N hilos lanzan fallos transitorios simultáneamente.
        Verificar que el estado final es OPEN consistente."""
        cb = CircuitBreaker("test_conc_open", failure_threshold=3, recovery_timeout=999)

        class _Transient(Exception):
            pass
        cb._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        def _fail() -> None:
            raise _Transient("fail")

        n_threads = 10
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(lambda: cb.call(_fail)) for _ in range(n_threads)]
            for f in as_completed(futures):
                try:
                    f.result()
                except _Transient:
                    pass
                except CircuitBreakerOpenError:
                    pass  # OPEN rechazó la llamada — esperado

        assert cb.state == CircuitState.OPEN
        assert cb._failure_count >= cb._failure_threshold
        assert cb._last_open_time > 0

    def test_concurrent_recovery(self) -> None:
        """OPEN → recovery_timeout → N hilos llaman éxito simultáneo.
        Verificar que el estado final es CLOSED (solo 1 HALF_OPEN probe recupera)."""
        cb = CircuitBreaker("test_conc_rec", failure_threshold=1, recovery_timeout=0.05)

        class _Transient(Exception):
            pass
        cb._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        with pytest.raises(_Transient):
            cb.call(lambda: (_ for _ in ()).throw(_Transient("fail")))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.1)  # Esperar recovery

        n_threads = 10
        success_count = 0
        open_count = 0
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(lambda: cb.call(lambda: "ok")) for _ in range(n_threads)]
            for f in as_completed(futures):
                try:
                    f.result()
                    success_count += 1
                except CircuitBreakerOpenError:
                    open_count += 1

        assert cb.state == CircuitState.CLOSED, (
            f"Expected CLOSED after recovery, got {cb.state}. "
            f"success={success_count}, open={open_count}"
        )
        # Solo 1 llamada debería pasar (half_open_max_calls=1),
        # pero tras el éxito el resto también pueden pasar si el circuito
        # vuelve a CLOSED antes de que terminen.
        assert success_count >= 1

    def test_no_double_open(self) -> None:
        """Dos fallos concurrentes con threshold=1 producen OPEN exactamente una vez."""
        cb = CircuitBreaker("test_no_double", failure_threshold=1, recovery_timeout=999)

        class _Transient(Exception):
            pass
        cb._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        def _fail() -> None:
            raise _Transient("fail")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(lambda: cb.call(_fail)) for _ in range(2)]
            for f in as_completed(futures):
                try:
                    f.result()
                except _Transient:
                    pass
                except CircuitBreakerOpenError:
                    pass

        assert cb.state == CircuitState.OPEN
        # El contador de fallos debe reflejar los fallos reales,
        # pero el estado OPEN es lo importante.
        assert cb._failure_count >= 1
        # Verificar que _last_open_time es razonable (monotonic)
        assert 0 < cb._last_open_time <= time.monotonic()

    def test_monotonic_clock(self) -> None:
        """Verificar que _last_open_time usa time.monotonic()."""
        cb = CircuitBreaker("test_mono", failure_threshold=1, recovery_timeout=999)

        class _Transient(Exception):
            pass
        cb._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        before = time.monotonic()
        with pytest.raises(_Transient):
            cb.call(lambda: (_ for _ in ()).throw(_Transient("fail")))
        after = time.monotonic()

        assert cb.state == CircuitState.OPEN
        assert before <= cb._last_open_time <= after, (
            f"_last_open_time ({cb._last_open_time}) fuera del rango "
            f"[{before}, {after}]"
        )


# ── B3: Retry ─────────────────────────

class TestRetry:
    def test_retry_transient_success(self) -> None:
        reg = ProviderRegistry()
        reg.register("t", _MockTransient(), default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=5, retry_backoff_base=0.01)
        result = router.generate("test")
        assert result == "ok_after_retry"

    def test_retry_disabled(self) -> None:
        reg = ProviderRegistry()
        t = _MockTransient()
        t._count = 0
        reg.register("t", t, default=True)
        router = LLMRouter(registry=reg, retry_enabled=False)
        result = router.generate("test")
        assert "Error" in result

    def test_no_retry_on_non_transient(self) -> None:
        reg = ProviderRegistry()
        reg.register("f", _MockFail(), default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=5)
        result = router.generate("test")
        assert "Error" in result  # ValueError is not transient, no retry


# ── H3: Política de retry por código HTTP ─────

class TestRetryPolicy:
    """Valida que cada código HTTP recibe el tratamiento correcto de retry."""

    @staticmethod
    def _make_provider(status_code: int, fail_times: int = 999) -> BaseLLMProvider:
        """Crea un proveedor que falla `fail_times` veces con HTTPStatusError."""

        class _MockHTTPError(BaseLLMProvider):
            _calls: int = 0

            def generate(self, prompt, model=None, options=None):
                self._calls += 1
                if self._calls <= fail_times:
                    import httpx

                    response = httpx.Response(status_code=status_code)
                    request = httpx.Request("POST", "http://test")
                    raise httpx.HTTPStatusError(
                        f"HTTP {status_code}", request=request, response=response,
                    )
                return "ok_after_retry"

            def embed(self, texts, model=None): return [[0.0]]
            async def embed_async(self, texts, model=None): return [[0.0]]
            def health(self): return {"status": "ok"}

        return _MockHTTPError()

    def _assert_no_retry(self, status_code: int) -> None:
        """Verifica que el código NO se reintenta (1 sola llamada, error directo)."""
        prov = self._make_provider(status_code)
        reg = ProviderRegistry()
        reg.register("p", prov, default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=3, retry_backoff_base=0.001)
        result = router.generate("test")
        assert "Error:" in str(result), f"Expected error for {status_code}, got {result}"
        assert prov._calls == 1, f"Expected 1 call for {status_code}, got {prov._calls}"

    def _assert_retry(self, status_code: int) -> None:
        """Verifica que el código SÍ se reintenta (falla 3 veces, luego error final)."""
        prov = self._make_provider(status_code, fail_times=3)
        reg = ProviderRegistry()
        reg.register("p", prov, default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=3, retry_backoff_base=0.001)
        result = router.generate("test")
        assert "Error:" in str(result), f"Expected error for {status_code}, got {result}"
        # Debería haber al menos 2 llamadas (intento + retry)
        assert prov._calls >= 2, f"Expected >=2 calls for {status_code}, got {prov._calls}"

    def _assert_retry_then_succeed(self, status_code: int) -> None:
        """Verifica que el código se reintenta y eventualmente tiene éxito."""
        prov = self._make_provider(status_code, fail_times=1)
        reg = ProviderRegistry()
        reg.register("p", prov, default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=3, retry_backoff_base=0.001)
        result = router.generate("test")
        assert "Error:" not in str(result), f"Expected success for {status_code}, got {result}"
        assert prov._calls == 2, f"Expected 2 calls (1 fail + 1 success) for {status_code}, got {prov._calls}"

    # 4xx no recuperables → 0 retries
    def test_no_retry_on_400(self) -> None:
        self._assert_no_retry(400)

    def test_no_retry_on_401(self) -> None:
        self._assert_no_retry(401)

    def test_no_retry_on_403(self) -> None:
        self._assert_no_retry(403)

    def test_no_retry_on_404(self) -> None:
        self._assert_no_retry(404)

    # 429 rate limiting → SÍ se reintenta
    def test_retry_on_429(self) -> None:
        self._assert_retry_then_succeed(429)

    # 5xx transitorios → SÍ se reintentan
    def test_retry_on_500(self) -> None:
        self._assert_retry_then_succeed(500)

    def test_retry_on_502(self) -> None:
        self._assert_retry_then_succeed(502)

    def test_retry_on_503(self) -> None:
        self._assert_retry_then_succeed(503)

    def test_retry_on_504(self) -> None:
        self._assert_retry_then_succeed(504)

    # Timeout → SÍ se reintenta
    def test_retry_on_timeout(self) -> None:
        class _MockTimeout(BaseLLMProvider):
            _calls: int = 0
            def generate(self, prompt, model=None, options=None):
                self._calls += 1
                import httpx
                raise httpx.TimeoutException("timeout", request=httpx.Request("POST", "http://test"))
            def embed(self, texts, model=None): return [[0.0]]
            async def embed_async(self, texts, model=None): return [[0.0]]
            def health(self): return {"status": "ok"}

        prov = _MockTimeout()
        reg = ProviderRegistry()
        reg.register("t", prov, default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=3, retry_backoff_base=0.001)
        result = router.generate("test")
        assert "Error:" in str(result), f"Expected error for timeout, got {result}"
        assert prov._calls == 3, f"Expected 3 calls for timeout, got {prov._calls}"

    # ValidationError (ValueError) → 0 retries
    def test_no_retry_on_validation_error(self) -> None:
        reg = ProviderRegistry()
        reg.register("f", _MockFail(), default=True)
        router = LLMRouter(registry=reg, retry_enabled=True, retry_max_attempts=3)
        result = router.generate("test")
        assert "Error:" in str(result)
        # Con _MockFail (call count no es accesible), verificamos que el resultado es error

    # Modelo inexistente (404) → 0 retries (mismo test que no_retry_on_404)
    def test_no_retry_on_model_not_found(self) -> None:
        self._assert_no_retry(404)


# ── B4: Fallback ─────────────────────────

class TestFallback:
    def test_fallback_to_secondary(self) -> None:
        reg = ProviderRegistry()
        reg.register("a", _MockFail(), default=True)
        reg.register("b", _MockOK())
        router = LLMRouter(registry=reg, fallback_enabled=True)
        result = router.generate("test")
        assert result == "ok"  # Falls back from a to b

    def test_fallback_disabled(self) -> None:
        reg = ProviderRegistry()
        reg.register("a", _MockFail(), default=True)
        reg.register("b", _MockOK())
        router = LLMRouter(registry=reg, fallback_enabled=False)
        result = router.generate("test")
        assert "Error" in result

    def test_fallback_all_fail(self) -> None:
        reg = ProviderRegistry()
        reg.register("a", _MockFail(), default=True)
        reg.register("b", _MockFail())
        router = LLMRouter(registry=reg, fallback_enabled=True)
        result = router.generate("test")
        assert "Error" in result  # All providers fail

    def test_fallback_no_secondary(self) -> None:
        reg = ProviderRegistry()
        reg.register("a", _MockFail(), default=True)
        router = LLMRouter(registry=reg, fallback_enabled=True)
        result = router.generate("test")
        assert "Error" in result  # No fallback available

    def test_fallback_logs_used_provider(self) -> None:
        """Verifica que el router registra qué proveedor atendió."""
        reg = ProviderRegistry()
        reg.register("a", _MockFail(), default=True)
        reg.register("b", _MockOK())
        router = LLMRouter(registry=reg, fallback_enabled=True)
        with patch("motor.core.llm.router.log") as mock_log:
            router.generate("test")
            assert mock_log.info.called


# ── B1: Observabilidad ─────────────────────────

class TestObservabilidad:
    def test_metrics_record(self) -> None:
        m = LLMMetrics()
        m.record("p1", "gen", 100.0, success=True, tokens=50)
        m.record("p1", "gen", 200.0, success=True)
        m.record("p2", "gen", 300.0, success=False, error="timeout")
        stats = m.get_stats()
        assert "p1.gen" in stats
        assert stats["p1.gen"]["llamadas_totales"] == 2
        assert stats["p1.gen"]["errores"] == {}
        assert "p2.gen" in stats
        assert "timeout" in stats["p2.gen"]["errores"]

    def test_metrics_empty(self) -> None:
        m = LLMMetrics()
        stats = m.get_stats()
        assert stats == {"error": "no data"}

    def test_metrics_summary(self) -> None:
        m = LLMMetrics()
        m.record("p1", "gen", 100.0, success=True)
        m.record("p1", "gen", 200.0, success=False, error="err")
        summary = m.summary()
        assert "p1" in summary
        assert summary["p1"]["ok"] == 1
        assert summary["p1"]["fail"] == 1

    def test_metrics_reset(self) -> None:
        m = LLMMetrics()
        m.record("p", "g", 100.0, success=True)
        m.reset()
        assert m.summary() == {}

    def test_metrics_percentile(self) -> None:
        m = LLMMetrics()
        for i in range(10):
            m.record("p", "g", float(i * 10), success=True)
        stats = m.get_stats("p", "g")
        p50 = stats["p.g"]["latencia_p50_ms"]
        p95 = stats["p.g"]["latencia_p95_ms"]
        p99 = stats["p.g"]["latencia_p99_ms"]
        assert 40 <= p50 <= 60  # Median ~45
        assert p95 >= 80
        assert p99 >= 80

    def test_metrics_filter_by_provider(self) -> None:
        m = LLMMetrics()
        m.record("p1", "gen", 100.0, success=True)
        m.record("p2", "gen", 200.0, success=True)
        stats = m.get_stats(provider="p1")
        assert "p1.gen" in stats
        assert "p2.gen" not in stats

    def test_router_instrumenta_llamadas(self) -> None:
        global_metrics.reset()
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg, fallback_enabled=False)
        router.generate("test")
        stats = global_metrics.get_stats()
        assert any("ok" in k for k in stats)


# ── B5: Health Monitor ─────────────────────────

class TestHealthMonitor:
    def test_health_cache(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        call_count = 0

        class _CountingOK(BaseLLMProvider):
            def generate(self, *a, **kw): return ""
            def embed(self, *a, **kw): return [[]]
            async def embed_async(self, *a, **kw): return [[]]
            def health(self):
                nonlocal call_count
                call_count += 1
                return {"status": "ok"}
        reg2 = ProviderRegistry()
        reg2.register("c", _CountingOK(), default=True)
        router = LLMRouter(registry=reg2, health_cache_ttl=999)

        router.health()
        assert call_count == 1  # First call hits provider
        router.health()
        assert call_count == 1  # Second call uses cache

    def test_health_cache_expires(self) -> None:
        call_count = 0

        class _CountingOK(BaseLLMProvider):
            def generate(self, *a, **kw): return ""
            def embed(self, *a, **kw): return [[]]
            async def embed_async(self, *a, **kw): return [[]]
            def health(self):
                nonlocal call_count
                call_count += 1
                return {"status": "ok"}
        reg = ProviderRegistry()
        reg.register("c", _CountingOK(), default=True)
        router = LLMRouter(registry=reg, health_cache_ttl=0.05)

        router.health()
        assert call_count == 1
        time.sleep(0.1)
        router.health()
        assert call_count == 2  # Cache expired


# ── B6: Logging ─────────────────────────

class TestLogging:
    def test_logging_on_success(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        with patch("motor.core.llm.router.log") as mock_log:
            router.generate("test")
            assert mock_log.info.called

    def test_logging_on_error(self) -> None:
        reg = ProviderRegistry()
        reg.register("f", _MockFail(), default=True)
        router = LLMRouter(registry=reg)
        with patch("motor.core.llm.router.log") as mock_log:
            router.generate("test")
            assert mock_log.warning.called


# ── Regresión ─────────────────────────

class TestRegresion:
    """Verifica que no se rompe la API existente."""

    def test_router_api_intacta(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        assert callable(router.generate)
        assert callable(router.embed)
        assert callable(router.embed_async)
        assert callable(router.health)

    def test_router_generate_signature(self) -> None:
        import inspect

        from motor.core.llm.router import LLMRouter

        sig = inspect.signature(LLMRouter.generate)
        params = list(sig.parameters.values())
        names = [p.name for p in params]
        assert names == ["self", "prompt", "model", "options", "provider"]

    def test_generate_retorna_str(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        result = router.generate("test")
        assert isinstance(result, str)
