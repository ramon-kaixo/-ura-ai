"""Circuit breaker — delegates to motor.platform.resilience (canonical).

Mantiene compatibilidad: call() lanza CircuitBreakerOpenError en OPEN.
"""

from motor.platform.resilience import (
    CircuitBreaker as _CircuitBreaker,
)
from motor.platform.resilience import (
    CircuitBreakerOpenError,
    CircuitState,
)


class CircuitBreaker(_CircuitBreaker):
    """Wrapper que lanza CircuitBreakerOpenError en lugar de retornar None."""

    def call(self, fn, *args, **kwargs):
        if not self.is_available:
            raise CircuitBreakerOpenError(self.name, max(0.0, self.recovery_timeout))
        return super().call(fn, *args, **kwargs)


__all__ = ["CircuitBreaker", "CircuitBreakerOpenError", "CircuitState"]
