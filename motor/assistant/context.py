"""ContextManager — 3 niveles de contexto con prioridad y expiración."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

from motor.assistant.context_window import ContextWindow
from motor.assistant.message_store import MessageStore
from motor.assistant.models import Message


class ContextLevel(IntEnum):
    IMMEDIATE = 3
    CONVERSATION = 2
    HISTORICAL = 1


@dataclass
class ContextItem:
    content: str
    level: ContextLevel
    source: str
    timestamp: str = ""
    priority: float = 1.0
    ttl_seconds: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        created = datetime.fromisoformat(self.timestamp)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        age = (datetime.now(UTC) - created).total_seconds()
        return age > self.ttl_seconds

    @property
    def score(self) -> float:
        return self.priority * self.level.value


class HistoricalMemoryAdapter:
    def __init__(self, memory: Any | None = None):
        self._memory = memory

    def query(self, query: str, limit: int = 10) -> list[ContextItem]:
        if self._memory is None:
            return []
        from motor.memory.models import MemoryEntry

        items: list[ContextItem] = []
        state = self._memory.state_at(datetime.now(UTC).timestamp())
        if state and isinstance(state, MemoryEntry):
            items.append(
                ContextItem(
                    content=str(state.data) if hasattr(state, "data") else str(state),
                    level=ContextLevel.HISTORICAL,
                    source="f26_memory",
                    priority=0.5,
                )
            )
        return items[:limit]

    def is_available(self) -> bool:
        return self._memory is not None


class ContextManager:
    def __init__(
        self,
        message_store: MessageStore | None = None,
        context_window: ContextWindow | None = None,
        historical_memory: HistoricalMemoryAdapter | None = None,
        max_immediate_turns: int = 10,
        max_conversation_items: int = 50,
        max_historical_items: int = 5,
        total_token_budget: int = 4096,
    ):
        self._store = message_store or MessageStore()
        self._window = context_window or ContextWindow(max_tokens=total_token_budget)
        self._historical = historical_memory or HistoricalMemoryAdapter()
        self._max_immediate = max_immediate_turns
        self._max_conversation = max_conversation_items
        self._max_historical = max_historical_items
        self._budget = total_token_budget

    def assemble(
        self,
        conversation_id: str,
        system_prompt: str = "",
        query: str = "",
    ) -> list[Message]:
        items: list[ContextItem] = []

        items.extend(self._get_immediate(conversation_id))
        items.extend(self._get_conversation_history(conversation_id))
        items.extend(self._get_historical(query))

        items.sort(key=lambda x: x.score, reverse=True)
        items = [i for i in items if not i.is_expired]

        budget = self._budget - (len(system_prompt) // 4 + 1) if system_prompt else self._budget
        return self._items_to_messages(items, budget)

    def _get_immediate(self, conversation_id: str) -> list[ContextItem]:
        messages = self._store.get_conversation(conversation_id, limit=self._max_immediate)
        return [
            ContextItem(
                content=f"{m.role}: {m.content}",
                level=ContextLevel.IMMEDIATE,
                source="immediate",
                timestamp=m.timestamp,
            )
            for m in messages
        ]

    def _get_conversation_history(self, conversation_id: str) -> list[ContextItem]:
        messages = self._store.get_conversation(conversation_id, limit=self._max_conversation)
        return [
            ContextItem(
                content=f"[{m.timestamp[:10]}] {m.role}: {m.content[:200]}",
                level=ContextLevel.CONVERSATION,
                source="conversation_history",
                timestamp=m.timestamp,
                priority=0.7,
                ttl_seconds=86400 * 7,
            )
            for m in messages
        ]

    def _get_historical(self, query: str) -> list[ContextItem]:
        if not query or not self._historical.is_available():
            return []
        return self._historical.query(query, limit=self._max_historical)

    def _items_to_messages(self, items: list[ContextItem], budget: int) -> list[Message]:
        messages: list[Message] = []
        total = 0
        for item in items:
            cost = len(item.content) // 4 + 1
            if total + cost > budget:
                break
            role = "system" if item.level == ContextLevel.HISTORICAL else "user"
            messages.append(
                Message(
                    role=role,
                    content=item.content,
                    metadata={"source": item.source, "level": item.level.name.lower()},
                )
            )
            total += cost
        return messages
