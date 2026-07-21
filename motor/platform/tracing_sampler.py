"""Trace Sampling — estrategias de muestreo para tracing distribuido.

Extraido de motor/platform/tracing.py para reducir tamaño del archivo.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SamplingStrategy(StrEnum):
    ALWAYS = "always"
    NEVER = "never"
    PROBABILISTIC = "probabilistic"
    ADAPTIVE = "adaptive"
    PRIORITY = "priority"


@dataclass
class Sampler:
    strategy: SamplingStrategy = SamplingStrategy.ALWAYS
    probability: float = 0.1
    error_rate_window: int = 100
    adaptive_min_p: float = 0.05
    adaptive_max_p: float = 1.0

    _recent_errors: list[bool] = field(default_factory=list)

    def should_sample(self, tags: dict[str, str] | None = None) -> bool:
        if self.strategy == SamplingStrategy.ALWAYS:
            return True
        if self.strategy == SamplingStrategy.NEVER:
            return False
        if self.strategy == SamplingStrategy.PROBABILISTIC:
            return random.random() < self.probability
        if self.strategy == SamplingStrategy.ADAPTIVE:
            if self._recent_errors:
                rate = sum(self._recent_errors) / len(self._recent_errors)
                p = self.adaptive_min_p + (self.adaptive_max_p - self.adaptive_min_p) * rate
                return random.random() < p
            return random.random() < self.adaptive_min_p
        if self.strategy == SamplingStrategy.PRIORITY:
            tags = tags or {}
            return tags.get("priority", "normal") in ("critical", "high")
        return True

    def record_error(self, was_error: bool) -> None:
        self._recent_errors.append(was_error)
        if len(self._recent_errors) > self.error_rate_window:
            self._recent_errors.pop(0)


# Tag sanitization constants
FORBIDDEN_TAG_EXACT: tuple[str, ...] = ("password", "secret", "token", "key", "auth", "api_key", "apikey")
FORBIDDEN_TAG_PREFIXES: tuple[str, ...] = ("password_", "secret_", "token_", "key_", "auth_", "private_")
MAX_TAG_KEY_LENGTH = 64
MAX_TAG_VAL_LENGTH = 256
MAX_TAGS_PER_EVENT = 32


def sanitize_tags(tags: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for k, v in tags.items():
        k_lower = k.lower().strip()
        if k_lower in FORBIDDEN_TAG_EXACT:
            continue
        if any(k_lower.startswith(p) for p in FORBIDDEN_TAG_PREFIXES):
            continue
        k_clean = k[:MAX_TAG_KEY_LENGTH]
        v_clean = v[:MAX_TAG_VAL_LENGTH]
        result[k_clean] = v_clean
        if len(result) >= MAX_TAGS_PER_EVENT:
            break
    return result
