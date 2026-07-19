"""Context window management with token budget."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.assistant.models import Message


class ContextWindow:
    def __init__(self, max_tokens: int = 4096, reserve_tokens: int = 1024):
        self._max_tokens = max_tokens
        self._reserve_tokens = reserve_tokens
        self._budget = max_tokens - reserve_tokens

    def build_context(self, messages: list[Message], system_prompt: str = "") -> list[Message]:
        system_cost = len(system_prompt) // 4 + 1 if system_prompt else 0
        available = self._budget - system_cost

        selected: list[Message] = []
        total = 0

        for msg in reversed(messages):
            cost = msg.token_estimate()
            if total + cost > available:
                break
            selected.insert(0, msg)
            total += cost

        return selected

    def trim_to_budget(self, messages: list[Message], max_tokens: int | None = None) -> list[Message]:
        budget = max_tokens or self._budget
        selected: list[Message] = []
        total = 0

        for msg in reversed(messages):
            cost = msg.token_estimate()
            if total + cost > budget:
                break
            selected.insert(0, msg)
            total += cost

        return selected
