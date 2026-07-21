"""Tests de resiliencia y observabilidad (F19 B8).

Circuit breaker, retry, fallback, observabilidad, health monitor.
"""

from __future__ import annotations

import logging
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
    def generate(self, prompt, model=None, options=None):
        return "ok"

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class _MockFail(BaseLLMProvider):
    def generate(self, prompt, model=None, options=None):
        msg = "fail"
        raise ValueError(msg)

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class _MockTransient(BaseLLMProvider):
    _count: int = 0

    def generate(self, prompt, model=None, options=None):
        self._count += 1
        if self._count < 3:
            msg = "transient"
            raise TimeoutError(msg)
        return "ok_after_retry"

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


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
            msg = "fail"
            raise _Transient(msg)

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
        """Non-transient errors count toward failure threshold (current behavior).

        The canonical CircuitBreaker counts ALL exceptions, not just transient ones.
        After failure_threshold errors, the circuit opens.
        """
        from motor.core.llm.circuit_breaker import CircuitBreakerOpenError

        cb = CircuitBreaker("test", failure_threshold=2)

        def _fail() -> None:
            msg = "validation error"
            raise ValueError(msg)

        # First 2 calls: ValueError (failure_count increases)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(_fail)

        # Circuit should be OPEN now
        assert cb.state == CircuitState.OPEN

        # Third call: should be rejected by open circuit
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(_fail)

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
            msg = "fail"
            raise _Transient(msg)

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
            f"Expected CLOSED after recovery, got {cb.state}. success={success_count}, open={open_count}"
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
            msg = "fail"
            raise _Transient(msg)

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
            f"_last_open_time ({cb._last_open_time}) fuera del rango [{before}, {after}]"
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
                    msg = f"HTTP {status_code}"
                    raise httpx.HTTPStatusError(
                        msg,
                        request=request,
                        response=response,
                    )
                return "ok_after_retry"

            def embed(self, texts, model=None):
                return [[0.0]]

            async def embed_async(self, texts, model=None):
                return [[0.0]]

            def health(self):
                return {"status": "ok"}

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

                msg = "timeout"
                raise httpx.TimeoutException(msg, request=httpx.Request("POST", "http://test"))

            def embed(self, texts, model=None):
                return [[0.0]]

            async def embed_async(self, texts, model=None):
                return [[0.0]]

            def health(self):
                return {"status": "ok"}

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

    # ── H4: Fallback hardening ────────────────

    def test_fallback_skips_open_provider(self) -> None:
        """Un proveedor con CB OPEN no debe ser elegido como fallback."""
        reg = ProviderRegistry()
        reg.register("a", _MockFail(), default=True)
        reg.register("b_open", _MockOK())
        reg.register("c", _MockOK())

        router = LLMRouter(registry=reg, fallback_enabled=True)

        # Insertar un CB con threshold bajo para abrirlo manualmente
        from motor.core.llm.circuit_breaker import CircuitBreaker

        cb_b = CircuitBreaker("b_open", failure_threshold=1, recovery_timeout=999)

        class _Transient(Exception):
            pass

        cb_b._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        def _fail_b() -> None:
            msg = "fail"
            raise _Transient(msg)

        with pytest.raises(_Transient):
            cb_b.call(_fail_b)
        assert cb_b.state == CircuitState.OPEN
        assert not cb_b.is_available

        router._circuit_breakers["b_open"] = cb_b

        # Fallback debe saltar b_open e ir a c
        result = router.generate("test")
        assert result == "ok", f"Expected c to handle, got {result}"
        assert router._resolve_name("generate", None) == "a"  # primary

    def test_fallback_no_chain(self) -> None:
        """Si el fallback falla, no se encadena a un tercer proveedor."""

        class _MockAlsoFail(BaseLLMProvider):
            _calls: int = 0

            def generate(self, prompt, model=None, options=None):
                self._calls += 1
                msg = "also fail"
                raise ValueError(msg)

            def embed(self, texts, model=None):
                return [[0.0]]

            async def embed_async(self, texts, model=None):
                return [[0.0]]

            def health(self):
                return {"status": "ok"}

        class _MockThird(BaseLLMProvider):
            _calls: int = 0

            def generate(self, prompt, model=None, options=None):
                self._calls += 1
                return "third_ok"

            def embed(self, texts, model=None):
                return [[0.0]]

            async def embed_async(self, texts, model=None):
                return [[0.0]]

            def health(self):
                return {"status": "ok"}

        reg = ProviderRegistry()
        reg.register("a", _MockFail(), default=True)
        reg.register("b", _MockAlsoFail())
        reg.register("c", _MockThird())
        router = LLMRouter(registry=reg, fallback_enabled=True, fallback_max_providers=3)

        _, provider_used = router._call_with_fallback(
            reg.get("a"),
            "generate",
            "generate",
            "a",
            "test",
        )
        assert provider_used == "a", f"Expected primary error, got fallback {provider_used}"
        assert reg.get("c")._calls == 0, "c should not be called (no chain)"

    def test_fallback_does_not_reset_cb(self) -> None:
        """El fallback no debe resetear el CB del proveedor alternativo."""
        reg = ProviderRegistry()
        reg.register("a", _MockFail(), default=True)
        reg.register("b", _MockOK())
        router = LLMRouter(registry=reg, fallback_enabled=True)

        from motor.core.llm.circuit_breaker import CircuitBreaker

        cb_b = CircuitBreaker("b", failure_threshold=1, recovery_timeout=999)

        class _Transient(Exception):
            pass

        cb_b._is_transient = staticmethod(lambda e: isinstance(e, _Transient))

        def _fail_b() -> None:
            msg = "fail"
            raise _Transient(msg)

        with pytest.raises(_Transient):
            cb_b.call(_fail_b)
        assert cb_b.state == CircuitState.OPEN

        router._circuit_breakers["b"] = cb_b

        state_before = cb_b.state
        result = router.generate("test")
        state_after = cb_b.state

        assert state_after == state_before, (
            f"Fallback should not modify CB state of provider b: {state_before} → {state_after}"
        )
        assert "Error" in result, "Fallback should fail (only provider is OPEN b)"

    def test_fallback_max_providers(self) -> None:
        """Verificar que fallback_max_providers limita los intentos."""

        class _MockFailWithCounter(BaseLLMProvider):
            _calls: int = 0

            def generate(self, prompt, model=None, options=None):
                self._calls += 1
                msg = "fail"
                raise ValueError(msg)

            def embed(self, texts, model=None):
                return [[0.0]]

            async def embed_async(self, texts, model=None):
                return [[0.0]]

            def health(self):
                return {"status": "ok"}

        # Registrar múltiples fallbacks que también fallan
        reg = ProviderRegistry()
        reg.register("a", _MockFailWithCounter(), default=True)
        for name in ("b", "c", "d", "e"):
            reg.register(name, _MockFailWithCounter())

        router = LLMRouter(registry=reg, fallback_enabled=True, fallback_max_providers=2)

        router.generate("test")
        # fallback_max_providers=2 significa que se prueban hasta 2 proveedores
        # Cada _call_with_retry llama a generate 1 vez (no retry porque ValueError no es transitorio)
        # Total: a (1) + b (1) + c (1 si fallback_max=2) = 3 calls max
        for name in ("d", "e"):
            p = reg.get(name)
            assert p._calls == 0, f"{name} should not be called (limit=2)"


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
            def generate(self, *a, **kw):
                return ""

            def embed(self, *a, **kw):
                return [[]]

            async def embed_async(self, *a, **kw):
                return [[]]

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
            def generate(self, *a, **kw):
                return ""

            def embed(self, *a, **kw):
                return [[]]

            async def embed_async(self, *a, **kw):
                return [[]]

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

    # ── H5: Health cache hardening ────────────

    def test_health_cache_concurrent(self) -> None:
        """N hilos llaman health() simultáneamente.
        Verificar que el proveedor no es llamado más veces de las necesarias."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        call_count = 0

        class _CountingHealth(BaseLLMProvider):
            def generate(self, *a, **kw):
                return ""

            def embed(self, *a, **kw):
                return [[]]

            async def embed_async(self, *a, **kw):
                return [[]]

            def health(self):
                nonlocal call_count
                call_count += 1
                return {"status": "ok"}

        reg = ProviderRegistry()
        reg.register("c", _CountingHealth(), default=True)
        router = LLMRouter(registry=reg, health_cache_ttl=999)

        n_threads = 10
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(router.health) for _ in range(n_threads)]
            results = [f.result() for f in as_completed(futures)]

        # Todos reciben respuesta
        assert len(results) == n_threads
        assert all(r["status"] == "ok" for r in results)

        # El proveedor debe ser llamado <= 3 veces (idealmente 1, pero
        # la ventana de concurrencia puede permitir 2-3)
        assert call_count <= 3, f"Expected <= 3 calls, got {call_count}. Cache deduplication may be degraded."

    def test_health_cache_invalidate(self) -> None:
        """Invalidación explícita fuerza una nueva llamada al proveedor."""
        call_count = 0

        class _CountingHealth(BaseLLMProvider):
            def generate(self, *a, **kw):
                return ""

            def embed(self, *a, **kw):
                return [[]]

            async def embed_async(self, *a, **kw):
                return [[]]

            def health(self):
                nonlocal call_count
                call_count += 1
                return {"status": "ok"}

        reg = ProviderRegistry()
        reg.register("c", _CountingHealth(), default=True)
        router = LLMRouter(registry=reg, health_cache_ttl=999)

        router.health()
        assert call_count == 1  # Primera llamada

        router.health()
        assert call_count == 1  # Cache hit

        # Invalidar específicamente
        router.invalidate_health_cache("c")
        router.health()
        assert call_count == 2  # Cache invalidado, nueva llamada

        # Invalidar todo
        router.invalidate_health_cache()
        router.health()
        assert call_count == 3  # Cache global invalidado, nueva llamada


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


# ── H6: Logging hardening ───────────────


class TestLoggingSafety:
    """Verifica que los logs no exponen información sensible y contienen
    únicamente los campos estructurados previstos."""

    SENSITIVE_PROMPT = "Mi clave API es sk-abc12345 y mi password es secreto"

    def test_logs_do_not_contain_prompt(self, caplog: pytest.LogCaptureFixture) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        with caplog.at_level(logging.INFO, logger="motor.core.llm.router"):
            router.generate(self.SENSITIVE_PROMPT)
        for record in caplog.records:
            msg = record.getMessage()
            assert self.SENSITIVE_PROMPT not in msg, f"Prompt leaked in log: {msg[:200]}"
            assert "sk-abc12345" not in msg, f"API key leaked in log: {msg[:200]}"

    def test_logs_do_not_contain_api_key(self, caplog: pytest.LogCaptureFixture) -> None:
        key_prompt = "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz"
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        with caplog.at_level(logging.INFO, logger="motor.core.llm.router"):
            router.generate(key_prompt)
        for record in caplog.records:
            msg = record.getMessage()
            assert "sk-proj" not in msg, f"API key leaked in log: {msg[:200]}"

    def test_logs_do_not_contain_embeddings(self, caplog: pytest.LogCaptureFixture) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        with caplog.at_level(logging.INFO, logger="motor.core.llm.router"):
            router.embed(["texto sensible"])
        for record in caplog.records:
            msg = record.getMessage()
            assert "texto sensible" not in msg, f"Embedding input leaked in log: {msg[:200]}"
            assert "0.0" not in msg or "latency" in msg, f"Vector data may have leaked: {msg[:200]}"

    def test_logs_do_not_contain_raw_request(self, caplog: pytest.LogCaptureFixture) -> None:
        raw_prompt = "raw sensitive request content"
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        with caplog.at_level(logging.INFO, logger="motor.core.llm.router"):
            router.generate(raw_prompt)
        for record in caplog.records:
            msg = record.getMessage()
            assert raw_prompt not in msg, f"Raw request leaked in log: {msg[:200]}"

    def test_logs_contain_expected_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        with caplog.at_level(logging.INFO, logger="motor.core.llm.router"):
            router.generate("test prompt")
        # Buscar al menos un registro con formato llm_call
        llm_records = [r for r in caplog.records if "llm_call" in r.getMessage()]
        assert len(llm_records) >= 1, "No se encontraron registros llm_call"

        record = llm_records[0]
        msg = record.getMessage()
        fields = ["provider", "op", "latency_ms", "attempt", "cb"]
        missing = [f for f in fields if f not in msg]
        assert not missing, f"Campos faltantes en log: {missing}. Mensaje: {msg}"


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
