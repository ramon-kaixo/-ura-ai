"""Tests for core/circuit_breaker.py — Circuit Breaker pattern."""

import logging
from unittest.mock import patch

import pytest

logging.disable(logging.CRITICAL)


@pytest.fixture(autouse=True)
def mock_auto_repair():
    """Prevent import of error_auto_repair during CB tests."""
    with patch("core.circuit_breaker.ErrorAutoRepair", side_effect=ImportError, create=True):
        yield


class TestInitialState:
    """CircuitBreaker empieza en estado CLOSED."""

    def test_imports_without_error(self):
        from core.circuit_breaker import CircuitBreaker

        assert CircuitBreaker is not None

    def test_starts_closed(self):
        from core.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_agent")
        assert cb.state == CircuitState.CLOSED

    def test_failure_count_starts_zero(self):
        from core.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test_agent")
        assert cb.failure_count == 0

    def test_custom_threshold_accepted(self):
        from core.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test", failure_threshold=5, timeout_seconds=30)
        assert cb.failure_threshold == 5
        assert cb.timeout_seconds == 30


class TestOpenAfterFailures:
    """Tras N fallos pasa a estado OPEN."""

    def test_opens_after_threshold_failures(self):
        from core.circuit_breaker import CircuitBreaker, CircuitState

        def _failing_func():
            raise RuntimeError("simulated failure")

        cb = CircuitBreaker("test_agent", failure_threshold=3)

        for i in range(3):
            with pytest.raises(RuntimeError, match="simulated failure"):
                cb.call(_failing_func)

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3


class TestBlocksCallsWhenOpen:
    """En OPEN rechaza llamadas sin ejecutarlas."""

    def test_rejects_calls_when_open(self):
        from core.circuit_breaker import CircuitBreaker, CircuitState

        def _failing_func():
            raise RuntimeError("fail")

        cb = CircuitBreaker("test_agent", failure_threshold=1, timeout_seconds=600)
        with pytest.raises(RuntimeError):
            cb.call(_failing_func)
        assert cb.state == CircuitState.OPEN

        called = [False]

        def _never_called():
            called[0] = True
            return "ok"

        result = cb.call(_never_called)
        assert result is None
        assert called[0] is False, "Function should not have been called when circuit is OPEN"


class TestSemiOpenAfterTimeout:
    """Tras timeout pasa a SEMI_OPEN."""

    def test_transitions_to_semi_open_after_timeout(self):
        from core.circuit_breaker import CircuitBreaker, CircuitState

        def _failing_func():
            raise RuntimeError("fail")

        cb = CircuitBreaker("test_agent", failure_threshold=1, timeout_seconds=0)
        with pytest.raises(RuntimeError):
            cb.call(_failing_func)
        assert cb.state == CircuitState.OPEN

        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.state == CircuitState.CLOSED


class TestSuccessfulCall:
    """Llamadas exitosas no incrementan fallos."""

    def test_successful_call_returns_result(self):
        from core.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_agent")
        result = cb.call(lambda x: x * 2, 21)
        assert result == 42
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
