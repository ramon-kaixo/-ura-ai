"""Circuit breaker — delegates to motor.platform.resilience (canonical)."""

from motor.platform.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
)

__all__ = ["CircuitBreaker", "CircuitBreakerOpenError"]
