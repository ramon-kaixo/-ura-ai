#!/usr/bin/env python3
"""Rate Limiter para Model Router - Previene abusos por IP"""

import time
from collections import defaultdict


class RateLimiter:
    """Rate limiter simple basado en sliding window."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        """Verifica si la IP puede hacer una petición."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Limpiar requests viejos
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if req_time > cutoff
        ]

        # Verificar límite
        if len(self.requests[client_ip]) >= self.max_requests:
            return False

        # Registrar request
        self.requests[client_ip].append(now)
        return True

    def get_remaining(self, client_ip: str) -> int:
        """Devuelve requests restantes para la IP."""
        now = time.time()
        cutoff = now - self.window_seconds

        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if req_time > cutoff
        ]

        return max(0, self.max_requests - len(self.requests[client_ip]))


# Instancia global del rate limiter
# 100 requests por minuto por IP
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
