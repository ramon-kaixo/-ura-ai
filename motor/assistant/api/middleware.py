"""Cross-cutting concerns: rate limiting, correlation_id, logging."""

from __future__ import annotations

import logging
import time

from fastapi import HTTPException

_log = logging.getLogger("ura.assistant.api")

_RATE_LIMIT_WINDOW = 60.0
_RATE_LIMIT_MAX = 60


class _RateLimiter:
    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}

    def check(self, key: str) -> None:
        now = time.monotonic()
        window_start = now - _RATE_LIMIT_WINDOW
        if key in self._requests:
            self._requests[key] = [t for t in self._requests[key] if t > window_start]
            if len(self._requests[key]) >= _RATE_LIMIT_MAX:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            self._requests[key].append(now)
        else:
            self._requests[key] = [now]


_rate_limiter = _RateLimiter()


def _scoped_cid(user_id: str, conversation_id: str) -> str:
    if user_id:
        return f"usr_{user_id[:16]}__{conversation_id}"
    return conversation_id
