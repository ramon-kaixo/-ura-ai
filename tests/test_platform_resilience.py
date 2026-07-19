"""Tests for motor/platform/resilience.py — CircuitBreaker + Backpressure."""

from __future__ import annotations

import threading
import time

import pytest

from motor.platform.resilience import (
    Backpressure,
    CircuitBreaker,
    CircuitState,
    get_backpressure,
    get_circuit_breaker,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OK = "ok"


def _succeed() -> str:
    return _OK


def _fail() -> str:
    msg = "boom"
    raise RuntimeError(msg)


# ---------------------------------------------------------------------------
# CircuitBreaker — state transitions
# ---------------------------------------------------------------------------


class TestCircuitBreakerStates:
    def test_initial_state_is_closed(self) -> None:
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_success_stays_closed(self) -> None:
        cb = CircuitBreaker("test")
        cb.call(_succeed)
        assert cb.state == CircuitState.CLOSED

    def test_failures_open_after_threshold(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=300.0)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(_fail)
        assert cb.state == CircuitState.OPEN

    def test_below_threshold_stays_closed(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=300.0)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(_fail)
        assert cb.state == CircuitState.CLOSED

    def test_open_returns_none(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=300.0)
        with pytest.raises(RuntimeError):
            cb.call(_fail)
        assert cb.call(_succeed) is None

    def test_half_open_after_recovery_timeout(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05)
        with pytest.raises(RuntimeError):
            cb.call(_fail)
        assert cb.state == CircuitState.OPEN
        time.sleep(0.06)
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_transitions_to_closed(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05)
        with pytest.raises(RuntimeError):
            cb.call(_fail)
        time.sleep(0.06)
        assert cb.state == CircuitState.HALF_OPEN
        result = cb.call(_succeed)
        assert result == _OK
        assert cb.state == CircuitState.CLOSED

    def test_reset_closes_circuit(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=300.0)
        with pytest.raises(RuntimeError):
            cb.call(_fail)
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._last_failure_time == 0.0

    def test_reset_allows_calls_again(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=300.0)
        with pytest.raises(RuntimeError):
            cb.call(_fail)
        cb.reset()
        result = cb.call(_succeed)
        assert result == _OK


# ---------------------------------------------------------------------------
# Backpressure
# ---------------------------------------------------------------------------


class TestBackpressure:
    def test_acquire_release(self) -> None:
        bp = Backpressure(max_queue=5, semaphore_count=5)
        assert bp.acquire(timeout=0.1) is True
        assert bp.size == 1
        bp.release()
        assert bp.size == 0

    def test_max_queue_blocks(self) -> None:
        bp = Backpressure(max_queue=3, semaphore_count=5)
        for _ in range(3):
            assert bp.acquire(timeout=0.1) is True
        assert bp.full is True
        assert bp.acquire(timeout=0.1) is False

    def test_release_frees_slot(self) -> None:
        bp = Backpressure(max_queue=2, semaphore_count=5)
        assert bp.acquire(timeout=0.1) is True
        assert bp.acquire(timeout=0.1) is True
        assert bp.acquire(timeout=0.1) is False
        bp.release()
        assert bp.size == 1
        assert bp.acquire(timeout=0.1) is True

    def test_full_property(self) -> None:
        bp = Backpressure(max_queue=2, semaphore_count=5)
        assert bp.full is False
        bp.acquire(timeout=0.1)
        assert bp.full is False
        bp.acquire(timeout=0.1)
        assert bp.full is True

    def test_release_empty_does_nothing(self) -> None:
        bp = Backpressure(max_queue=5, semaphore_count=5)
        bp.release()
        assert bp.size == 0

    def test_size_reflects_queue_depth(self) -> None:
        bp = Backpressure(max_queue=10, semaphore_count=5)
        assert bp.size == 0
        for i in range(1, 6):
            bp.acquire(timeout=0.1)
            assert bp.size == i
        for i in range(4, -1, -1):
            bp.release()
            assert bp.size == i


# ---------------------------------------------------------------------------
# Registry functions
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_get_circuit_breaker_creates_new(self) -> None:
        cb = get_circuit_breaker("reg-test")
        assert isinstance(cb, CircuitBreaker)
        assert cb.name == "reg-test"

    def test_get_circuit_breaker_returns_singleton(self) -> None:
        cb1 = get_circuit_breaker("singleton")
        cb2 = get_circuit_breaker("singleton")
        assert cb1 is cb2

    def test_get_circuit_breaker_different_names(self) -> None:
        cb1 = get_circuit_breaker("alpha")
        cb2 = get_circuit_breaker("beta")
        assert cb1 is not cb2

    def test_get_circuit_breaker_custom_params(self) -> None:
        cb = get_circuit_breaker("custom", failure_threshold=5, recovery_timeout=10.0)
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 10.0

    def test_get_backpressure_creates_new(self) -> None:
        bp = get_backpressure("reg-bp")
        assert isinstance(bp, Backpressure)
        assert bp.max_queue == 100

    def test_get_backpressure_returns_singleton(self) -> None:
        bp1 = get_backpressure("bp-singleton")
        bp2 = get_backpressure("bp-singleton")
        assert bp1 is bp2

    def test_get_backpressure_different_names(self) -> None:
        bp1 = get_backpressure("gamma")
        bp2 = get_backpressure("delta")
        assert bp1 is not bp2

    def test_get_backpressure_custom_max_queue(self) -> None:
        bp = get_backpressure("bp-custom", max_queue=50)
        assert bp.max_queue == 50


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestCircuitBreakerThreadSafety:
    def test_concurrent_calls_do_not_corrupt_state(self) -> None:
        cb = CircuitBreaker("concurrent", failure_threshold=5, recovery_timeout=300.0)
        n = 100
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker() -> None:
            for _ in range(10):
                try:
                    cb.call(_succeed)
                except Exception as exc:
                    with lock:
                        errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cb.state == CircuitState.CLOSED

    def test_concurrent_failures_trigger_open(self) -> None:
        cb = CircuitBreaker("concurrent-fail", failure_threshold=5, recovery_timeout=300.0)
        n = 20
        errors: list[Exception] = []
        none_results: list[None] = []
        lock = threading.Lock()
        barrier = threading.Barrier(n)

        def worker() -> None:
            barrier.wait()
            try:
                result = cb.call(_fail)
            except RuntimeError as exc:
                with lock:
                    errors.append(exc)
            else:
                if result is None:
                    with lock:
                        none_results.append(result)

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) > 0
        assert len(errors) + len(none_results) == n
        assert cb.state == CircuitState.OPEN
        assert cb._failure_count >= 5


class TestBackpressureThreadSafety:
    def test_concurrent_acquire_release(self) -> None:
        bp = Backpressure(max_queue=100, semaphore_count=50)
        n = 50
        acquired = [0]
        lock = threading.Lock()

        def worker() -> None:
            if bp.acquire(timeout=5.0):
                with lock:
                    acquired[0] += 1
                time.sleep(0.005)
                bp.release()

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert acquired[0] == n
        assert bp.size == 0

    def test_concurrent_full_pressure(self) -> None:
        bp = Backpressure(max_queue=5, semaphore_count=5)
        acquired_count = [0]
        lock = threading.Lock()

        def worker() -> None:
            if bp.acquire(timeout=0.5):
                with lock:
                    acquired_count[0] += 1
                time.sleep(0.02)
                bp.release()

        n = 50
        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert acquired_count[0] == n


class TestRegistryThreadSafety:
    def test_get_circuit_breaker_concurrent(self) -> None:
        results: list[CircuitBreaker] = []
        lock = threading.Lock()

        def worker() -> None:
            cb = get_circuit_breaker("race")
            with lock:
                results.append(cb)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
        first = results[0]
        assert all(r is first for r in results)

    def test_get_backpressure_concurrent(self) -> None:
        results: list[Backpressure] = []
        lock = threading.Lock()

        def worker() -> None:
            bp = get_backpressure("race-bp")
            with lock:
                results.append(bp)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
        first = results[0]
        assert all(r is first for r in results)
