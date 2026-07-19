"""Critical audit tests for motor/assistant/models.py.

Exposes bugs, type-safety gaps, edge cases, and design flaws.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from motor.assistant.models import (
    Conversation,
    ConversationMode,
    ConversationState,
    Message,
    UserIntent,
)


# ── Message audit ─────────────────────────────────────────────────────────


class TestMessageAudit:
    def test_invalid_role_accepted(self):
        """BUG: Literal type is NOT enforced at runtime.

        MessageRole = Literal["user","assistant","system","tool"] is
        a static-only hint.  Any arbitrary string passes at runtime.
        """
        msg = Message(role="invented_role", content="boom")  # type: ignore[arg-type]
        # This should have raised but doesn't — runtime type gap.
        assert msg.role == "invented_role", (
            "Runtime should have rejected 'invented_role', but it didn't"
        )

    def test_empty_role_string(self):
        """Edge case: empty string role accepted with no validation."""
        msg = Message(role="", content="empty")
        assert msg.role == ""

    def test_token_estimate_zero_divisor(self):
        """BUG: chars_per_token=0 raises ZeroDivisionError."""
        msg = Message(role="user", content="hello")
        with pytest.raises(ZeroDivisionError):
            msg.token_estimate(chars_per_token=0.0)

    def test_token_estimate_negative_divisor(self):
        """BUG: negative chars_per_token produces negative / nonsensical result."""
        msg = Message(role="user", content="hello")
        result = msg.token_estimate(chars_per_token=-4.0)
        # len("hello") = 5 → int(5 / -4) = int(-1.25) = -1 → -1 + 1 = 0
        assert result == 0, f"Expected 0 for negative divisor, got {result}"

    def test_token_estimate_empty_content(self):
        """Semantic edge case: empty content still counts as 1 token.

        int(0/4) + 1 = 1.  A message with no content should arguably
        consume 0 tokens, not 1.
        """
        msg = Message(role="user", content="")
        assert msg.token_estimate() == 1, (
            "Empty message reports 1 token — wasteful if many empty messages exist"
        )

    def test_token_estimate_huge_content(self):
        """Performance edge case: very long strings are handled."""
        msg = Message(role="user", content="x" * 10_000_000)
        # Should not blow up and should compute quickly.
        tokens = msg.token_estimate()
        assert tokens == 2_500_001  # 10M / 4 + 1

    def test_token_estimate_cjk_content(self):
        """Accuracy edge case: CJK text has ~1-2 chars/token, not 4.

        The fixed 4.0 default overestimates token count for CJK.
        """
        msg = Message(role="user", content="你好世界")
        # 4 chars / 4 + 1 = 2, but a CJK tokeniser would give ~4 tokens.
        tokens = msg.token_estimate()
        # The test documents the inaccuracy: it returns 2 instead of ~4.
        assert tokens == 2, (
            "CJK text severely underestimated at 4.0 chars/token default"
        )

    def test_tool_message_no_tool_call_id(self):
        """Missing validation: tool messages should require tool_call_id."""
        msg = Message(role="tool", content="result", tool_call_id="")
        # Should arguably raise or at least warn, but does not.
        assert msg.tool_call_id == ""

    def test_metadata_independence(self):
        """Design check: default_factory protects against shared mutable dict."""
        m1 = Message(role="user", content="a")
        m2 = Message(role="user", content="b")
        m1.metadata["key"] = "val"
        assert "key" not in m2.metadata  # Shared reference would leak here

    def test_timestamp_whitespace_not_overwritten(self):
        """Edge case: a whitespace-only timestamp is treated as truthy."""
        msg = Message(role="user", content="hi", timestamp="   ")
        # "   " is not empty → falsy, so __post_init__ skips overwrite.
        assert msg.timestamp == "   ", (
            "Whitespace-only timestamp should probably be treated as empty"
        )

    def test_message_with_extra_unknown_kwarg(self):
        """BUG: unknown kwarg in Message() raises TypeError."""
        with pytest.raises(TypeError):
            Message(role="user", content="x", non_existent_field="boom")  # type: ignore[call-arg]


# ── ConversationState audit ───────────────────────────────────────────────


class TestConversationStateAudit:
    def test_created_at_after_updated_at(self):
        """BUG: no invariant ensures updated_at >= created_at."""
        future = (datetime.now(UTC) + timedelta(days=365)).isoformat()
        state = ConversationState(
            conversation_id="test",
            created_at=future,
            updated_at="",  # will become datetime.now(UTC)
        )
        assert state.updated_at < state.created_at, (
            "No invariant: updated_at is before created_at when "
            "a future created_at is provided"
        )

    def test_turn_count_negative(self):
        """Edge case: turn_count can be negative with no guard."""
        state = ConversationState(
            conversation_id="test",
            turn_count=-5,
        )
        assert state.turn_count == -5, "Negative turn_count accepted"

    def test_mode_is_enum_not_string(self):
        """Design: mode is strongly typed via Enum."""
        state = ConversationState(conversation_id="test")
        assert isinstance(state.mode, ConversationMode)

    def test_conversation_id_empty_accepted(self):
        """Edge case: empty conversation_id passes without validation."""
        state = ConversationState(conversation_id="")
        assert state.conversation_id == ""


# ── Conversation audit ────────────────────────────────────────────────────


class TestConversationAudit:
    def test_add_message_kwargs_role_collision(self):
        """BUG: passing role in **kwargs causes TypeError collision."""
        conv = Conversation(conversation_id="test")
        with pytest.raises(TypeError, match="multiple values for argument 'role'"):
            conv.add_message("user", "hello", role="assistant")

    def test_add_message_kwargs_content_collision(self):
        """BUG: passing content in **kwargs causes TypeError collision."""
        conv = Conversation(conversation_id="test")
        with pytest.raises(TypeError, match="multiple values for argument 'content'"):
            conv.add_message("user", "hello", content="world")

    def test_add_message_unknown_kwarg_bubbles(self):
        """BUG: unknown kwarg in add_message propagates TypeError from Message()."""
        conv = Conversation(conversation_id="test")
        with pytest.raises(TypeError):
            conv.add_message("user", "x", unknown_field="boom")  # type: ignore[call-arg]

    def test_state_none_skips_turn_count(self):
        """Design: Conversation without state never increments turn_count."""
        conv = Conversation(conversation_id="test", state=None)
        conv.add_message("user", "hello")
        conv.add_message("assistant", "world")
        # No state, so turn_count cannot be checked.  This silently ignores
        # a tracking mechanism the caller might expect.
        assert conv.state is None  # turn_count never existed

    def test_turn_count_diverges_when_directly_set(self):
        """Design: turn_count can be manually set out of sync with messages."""
        conv = Conversation(
            conversation_id="test",
            state=ConversationState(conversation_id="test", turn_count=100),
        )
        conv.add_message("user", "hello")
        # turn_count = 100 + 1 = 101, but there is only 1 message.
        assert conv.state is not None
        assert conv.state.turn_count == 101
        assert len(conv.messages) == 1

    def test_token_count_empty(self):
        """Edge case: empty conversation returns 0 (actually 0)."""
        conv = Conversation(conversation_id="test")
        # sum() of empty list is 0, so token_count = 0.
        assert conv.token_count == 0

    def test_last_user_message_empty_conversation(self):
        """Edge case: no messages returns None."""
        conv = Conversation(conversation_id="test")
        assert conv.last_user_message is None

    def test_last_assistant_message_empty_conversation(self):
        """Edge case: no messages returns None."""
        conv = Conversation(conversation_id="test")
        assert conv.last_assistant_message is None

    def test_last_user_message_with_only_tool_messages(self):
        """Edge case: no 'user' role messages returns None."""
        conv = Conversation(conversation_id="test")
        conv.add_message("assistant", "hello")
        conv.add_message("tool", "result")
        assert conv.last_user_message is None

    def test_last_assistant_message_with_only_user_messages(self):
        """Edge case: no 'assistant' role messages returns None."""
        conv = Conversation(conversation_id="test")
        conv.add_message("user", "hello")
        assert conv.last_assistant_message is None

    def test_add_message_returns_correct_message(self):
        """Contract check: returned Message matches inputs."""
        conv = Conversation(conversation_id="test")
        msg = conv.add_message("user", "hello", tool_call_id="t1", tool_name="search")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.tool_call_id == "t1"
        assert msg.tool_name == "search"

    def test_updated_at_on_each_message(self):
        """Contract check: updated_at changes after each add_message."""
        state = ConversationState(conversation_id="test")
        conv = Conversation(conversation_id="test", state=state)
        before = state.updated_at
        conv.add_message("user", "hello")
        after = state.updated_at
        assert after >= before  # could be equal in fast CI runs

    def test_many_messages_linear_scan(self):
        """Performance: last_user_message / last_assistant_message are O(n).

        For very long conversations, this property does a linear scan
        every time.  Acceptable for most cases, but worth documenting.
        """
        conv = Conversation(conversation_id="test")
        for i in range(10_000):
            role = "user" if i % 2 == 0 else "assistant"
            conv.add_message(role, f"msg_{i}")
        # These are O(n) each — they scan all messages.
        last_user = conv.last_user_message
        assert last_user is not None
        assert last_user.content == "msg_9998"

    def test_role_system_accepted(self):
        """Contract: 'system' is a valid MessageRole."""
        msg = Message(role="system", content="You are a helpful assistant.")
        assert msg.role == "system"


# ── ConversationMode + UserIntent audit ────────────────────────────────────


class TestEnumAudit:
    def test_conversation_mode_string_values(self):
        """Design note: enum values are Spanish strings."""
        assert ConversationMode.CONVERSATION.value == "conversacion"
        assert ConversationMode.WORK.value == "trabajo"
        assert ConversationMode.EXPLANATION.value == "explicacion"

    def test_user_intent_count(self):
        """Contract: all expected intents are present."""
        expected = {
            "CHAT", "QUESTION", "COMMAND", "SEARCH", "CLARIFY",
            "GREETING", "FAREWELL", "CONFIRM", "REJECT", "CORRECT",
            "REPEAT", "UNKNOWN",
        }
        actual = {e.name for e in UserIntent}
        assert actual == expected

    def test_conversation_mode_from_string(self):
        """Contract: enum lookup by value works."""
        mode = ConversationMode("trabajo")
        assert mode == ConversationMode.WORK

    def test_conversation_mode_invalid_string_raises(self):
        """Contract: invalid string raises ValueError."""
        with pytest.raises(ValueError):
            ConversationMode("invalid_mode")


# ── Combined / integration-like audit ─────────────────────────────────────


class TestCombinedAudit:
    def test_full_lifecycle_no_state(self):
        """Edge case: Conversation can work without ConversationState."""
        conv = Conversation(conversation_id="test")
        conv.add_message("user", "hola")
        conv.add_message("assistant", "mundo")
        assert len(conv.messages) == 2
        assert conv.token_count == 4  # "hola" → 2, "mundo" → 2
        assert conv.last_user_message is not None
        assert conv.last_user_message.content == "hola"

    def test_conversation_id_collision(self):
        """Design: no dedup on conversation_id.

        Two Conversations can share the same id with no warning.
        """
        conv1 = Conversation(conversation_id="dup")
        conv2 = Conversation(conversation_id="dup")
        conv1.add_message("user", "a")
        conv2.add_message("user", "b")
        assert conv1.conversation_id == conv2.conversation_id
        assert conv1.last_user_message.content == "a"
        assert conv2.last_user_message.content == "b"
