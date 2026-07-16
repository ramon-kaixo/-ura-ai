"""Circuit breaker por proveedor.

Estados: CLOSED → OPEN → HALF_OPEN → CLOSED|OPEN
Thread-safe mediante threading.Lock.
"""

from __future__ import annotations

import threading
import time
from enum import Enum


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
    """Circuit breaker independiente por proveedor.

    Configuración desde CONFIG["llm"]["circuit_breaker"]:
        failure_threshold: fallos consecutivos para abrir (default: 5)
        recovery_timeout: segundos antes de HALF_OPEN (default: 30)
        half_open_max_calls: llamadas de prueba en HALF_OPEN (default: 1)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_open_time: float = 0.0
        self._half_open_calls: int = 0
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    @property
    def is_available(self) -> bool:
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                return time.monotonic() - self._last_open_time >= self._recovery_timeout
            return True  # HALF_OPEN permite una llamada

    def _try_acquire(self) -> bool:
        """Intenta adquirir permiso para realizar una llamada.
        Retorna True si la llamada puede proceder."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_open_time >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._half_open_calls += 1
                    return True
                return False
            if self._half_open_calls < self._half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

    def call(self, fn, *args, **kwargs):
        """Ejecuta fn si el circuito lo permite. Lanza CircuitBreakerOpenError si OPEN."""
        if not self._try_acquire():
            remaining = (self._last_open_time + self._recovery_timeout) - time.monotonic()
            raise CircuitBreakerOpenError(self._name, max(0.0, remaining))
        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            if self._is_transient(e):
                self._on_failure()
            raise

    def _on_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._half_open_calls = 0

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._state == CircuitState.HALF_OPEN or self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN
                self._last_open_time = time.monotonic()

    @staticmethod
    def _is_transient(exception: Exception) -> bool:
        """Determina si un error es recuperable (transitorio) o no."""
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

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_open_time = 0.0

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self._name!r}, state={self._state.value}, "
            f"failures={self._failure_count})"
        )
