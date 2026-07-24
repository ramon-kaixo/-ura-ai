"""CircuitBreaker + escalado para pipelines."""
from __future__ import annotations

import time
from typing import Any


class CircuitBreaker:
    """Protege pipelines contra fallos repetidos.

    closed → open tras 3 fallos consecutivos
    open → rechaza llamadas durante `timeout` segundos
    half-open → permite reintentar despues del timeout
    """

    def __init__(self, max_failures: int = 3, timeout: int = 300) -> None:
        self.max_failures = max_failures
        self.timeout = timeout
        self.failures = 0
        self.state = "closed"
        self.last_failure: float = 0.0

    def call(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        now = time.time()
        if self.state == "open":
            if now - self.last_failure > self.timeout:
                self.state = "half-open"
            else:
                raise RuntimeError(f"Circuit breaker OPEN for {self.timeout}s")
        try:
            result = fn(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failures = 0
            return result
        except Exception:
            self.failures += 1
            self.last_failure = now
            if self.state == "half-open" or self.failures >= self.max_failures:
                self.state = "open"
            raise

    def reset(self) -> None:
        self.state = "closed"
        self.failures = 0
