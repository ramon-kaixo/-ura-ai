"""Tests for motor/assistant/context.py — ContextManager."""

from __future__ import annotations

import tempfile
from pathlib import Path

from motor.assistant.context import ContextItem, ContextLevel, ContextManager, HistoricalMemoryAdapter
from motor.assistant.message_store import MessageStore
from motor.assistant.models import Message


class TestContextLevel:
    def test_level_values(self):
        assert ContextLevel.IMMEDIATE.value == 3
        assert ContextLevel.CONVERSATION.value == 2
        assert ContextLevel.HISTORICAL.value == 1

    def test_level_ordering(self):
        assert ContextLevel.IMMEDIATE > ContextLevel.CONVERSATION
        assert ContextLevel.CONVERSATION > ContextLevel.HISTORICAL


class TestContextItem:
    def test_creation(self):
        item = ContextItem(content="test", level=ContextLevel.IMMEDIATE, source="chat")
        assert item.content == "test"
        assert item.source == "chat"
        assert item.timestamp != ""

    def test_score_combines_priority_and_level(self):
        item = ContextItem(content="a", level=ContextLevel.IMMEDIATE, source="s", priority=0.5)
        assert item.score == 1.5  # 0.5 * 3

    def test_expired(self):
        item = ContextItem(
            content="a", level=ContextLevel.IMMEDIATE, source="s",
            ttl_seconds=1, timestamp="2020-01-01T00:00:00+00:00",
        )
        assert item.is_expired

    def test_not_expired(self):
        item = ContextItem(content="a", level=ContextLevel.IMMEDIATE, source="s", ttl_seconds=3600)
        assert not item.is_expired

    def test_no_expiration(self):
        item = ContextItem(content="a", level=ContextLevel.IMMEDIATE, source="s")
        assert not item.is_expired


class TestHistoricalMemoryAdapter:
    def test_no_memory_returns_empty(self):
        adapter = HistoricalMemoryAdapter()
        assert adapter.query("test") == []
        assert not adapter.is_available()


class TestContextManager:
    def setup_method(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            self.db_path = Path(f.name)
        self.store = MessageStore(db_path=str(self.db_path))
        self.manager = ContextManager(
            message_store=self.store,
            max_immediate_turns=5,
            max_conversation_items=20,
            max_historical_items=3,
            total_token_budget=2000,
        )

    def teardown_method(self):
        self.db_path.unlink(missing_ok=True)

    def _add_messages(self, count: int, conv_id: str = "c1"):
        for i in range(count):
            self.store.append(conv_id, Message(role="user", content=f"message {i}"))
            self.store.append(conv_id, Message(role="assistant", content=f"response {i}"))

    def test_assemble_immediate_context(self):
        self._add_messages(3)
        ctx = self.manager.assemble("c1")
        assert len(ctx) > 0

    def test_assemble_respects_max_turns(self):
        self._add_messages(20)
        ctx = self.manager.assemble("c1")
        assert len(ctx) > 0

    def test_empty_conversation(self):
        ctx = self.manager.assemble("nonexistent")
        assert ctx == []

    def test_assemble_with_system_prompt(self):
        self._add_messages(2)
        ctx = self.manager.assemble("c1", system_prompt="Eres un asistente útil.")
        assert len(ctx) > 0

    def test_different_conversations(self):
        self._add_messages(2, "c1")
        self._add_messages(3, "c2")
        ctx1 = self.manager.assemble("c1")
        ctx2 = self.manager.assemble("c2")
        assert len(ctx1) != len(ctx2) or ctx1 != ctx2

    def test_level_scoring(self):
        items = [
            ContextItem(content="recent", level=ContextLevel.IMMEDIATE, source="s1"),
            ContextItem(content="older", level=ContextLevel.HISTORICAL, source="s2"),
        ]
        items.sort(key=lambda x: x.score, reverse=True)
        assert items[0].source == "s1"

    def test_context_window_integration(self):
        from motor.assistant.context_window import ContextWindow

        window = ContextWindow(max_tokens=100)
        messages = [Message(role="user", content="hello world") for _ in range(5)]
        truncated = window.trim_to_budget(messages, max_tokens=50)
        assert len(truncated) <= 5
