"""F29 B5 — Resiliencia: Circuit Breaker + Backpressure."""

from __future__ import annotations

import threading
import time
from enum import Enum
from threading import Lock
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """La llamada fue rechazada porque el circuit breaker está OPEN."""

    def __init__(self, provider: str, retry_after: float) -> None:
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker OPEN for '{provider}', retry in {retry_after:.0f}s")


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = Lock()

    @property
    def _last_open_time(self) -> float:
        return self._last_failure_time

    @property
    def _failure_threshold(self) -> int:
        return self.failure_threshold

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN and time.monotonic() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
            return self._state

    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T | None:
        st = self.state
        if st == CircuitState.OPEN:
            return None
        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._last_failure_time = time.monotonic()
            raise
        with self._lock:
            self._failure_count = 0
            if st == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
        return result

    @property
    def is_available(self) -> bool:
        return self.state != CircuitState.OPEN

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0


class Backpressure:
    def __init__(self, max_queue: int = 100, semaphore_count: int = 5) -> None:
        self.max_queue = max_queue

        self._sem = threading.Semaphore(semaphore_count)
        self._queue_size = 0
        self._lock = Lock()

    def acquire(self, timeout: float = 1.0) -> bool:
        if not self._sem.acquire(timeout=timeout):
            return False
        with self._lock:
            if self._queue_size < self.max_queue:
                self._queue_size += 1
                return True
            self._sem.release()
            return False

    def release(self) -> None:
        self._sem.release()
        with self._lock:
            self._queue_size = max(0, self._queue_size - 1)

    @property
    def size(self) -> int:
        with self._lock:
            return self._queue_size

    @property
    def full(self) -> bool:
        with self._lock:
            return self._queue_size >= self.max_queue


_CIRCUIT_BREAKERS: dict[str, CircuitBreaker] = {}
_BACKPRESSURE_INSTANCES: dict[str, Backpressure] = {}
_LOCK = Lock()


def get_circuit_breaker(name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0) -> CircuitBreaker:
    with _LOCK:
        if name not in _CIRCUIT_BREAKERS:
            _CIRCUIT_BREAKERS[name] = CircuitBreaker(name, failure_threshold, recovery_timeout)
        return _CIRCUIT_BREAKERS[name]


def get_backpressure(name: str, max_queue: int = 100) -> Backpressure:
    with _LOCK:
        if name not in _BACKPRESSURE_INSTANCES:
            _BACKPRESSURE_INSTANCES[name] = Backpressure(max_queue=max_queue)
        return _BACKPRESSURE_INSTANCES[name]
