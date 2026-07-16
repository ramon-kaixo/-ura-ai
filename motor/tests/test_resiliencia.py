"""Tests de resiliencia y observabilidad (F19 B8).

Circuit breaker, retry, fallback, observabilidad, health monitor.
"""

from __future__ import annotations

import time
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
