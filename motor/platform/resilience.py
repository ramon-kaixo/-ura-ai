"""F29 B5 — Resiliencia: Circuit Breaker + Backpressure."""

from __future__ import annotations

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


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._lock = Lock()

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
            with self._lock:
                self._failure_count = 0
                self._state = CircuitState.CLOSED
            return result
        except Exception:
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.monotonic()
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
            raise

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0


class Backpressure:
    def __init__(self, max_queue: int = 100, semaphore_count: int = 5) -> None:
        self.max_queue = max_queue
        self._queue: list[Any] = []
        self._lock = Lock()

    def acquire(self, timeout: float = 1.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if len(self._queue) < self.max_queue:
                    self._queue.append(object())
                    return True
            time.sleep(0.01)
        return False

    def release(self) -> None:
        with self._lock:
            if self._queue:
                self._queue.pop()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def full(self) -> bool:
        with self._lock:
            return len(self._queue) >= self.max_queue


# Global registry
_circuit_breakers: dict[str, CircuitBreaker] = {}
_backpressure_registry: dict[str, Backpressure] = {}
_lock = Lock()


def get_circuit_breaker(name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0) -> CircuitBreaker:
    with _lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name, failure_threshold, recovery_timeout)
        return _circuit_breakers[name]


def get_backpressure(name: str, max_queue: int = 100) -> Backpressure:
    with _lock:
        if name not in _backpressure_registry:
            _backpressure_registry[name] = Backpressure(max_queue=max_queue)
        return _backpressure_registry[name]
