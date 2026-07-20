"""Circuit breaker — delegates to motor.platform.resilience (canonical)."""

from motor.platform.resilience import (  # noqa: F401
    CircuitBreaker,
    CircuitBreakerOpenError,
)

__all__ = ["CircuitBreaker", "CircuitBreakerOpenError"]
