"""Models for the conversational assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

MessageRole = Literal["user", "assistant", "system", "tool"]


class ConversationMode(Enum):
    CONVERSATION = "conversacion"
    WORK = "trabajo"
    EXPLANATION = "explicacion"


class UserIntent(Enum):
    CHAT = "chat"
    QUESTION = "question"
    COMMAND = "command"
    SEARCH = "search"
    CLARIFY = "clarify"
    GREETING = "greeting"
    FAREWELL = "farewell"
    CONFIRM = "confirm"
    REJECT = "reject"
    CORRECT = "correct"
    REPEAT = "repeat"
    UNKNOWN = "unknown"


@dataclass
class Message:
    role: MessageRole
    content: str
    timestamp: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()

    def token_estimate(self, chars_per_token: float = 4.0) -> int:
        return int(len(self.content) / chars_per_token) + 1


@dataclass
class ConversationState:
    conversation_id: str
    mode: ConversationMode = ConversationMode.CONVERSATION
    active_goal: str = ""
    turn_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        now = datetime.now(UTC).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class Conversation:
    conversation_id: str
    messages: list[Message] = field(default_factory=list)
    state: ConversationState | None = None

    def add_message(self, role: MessageRole, content: str, **kwargs: Any) -> Message:
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        if self.state:
            self.state.turn_count += 1
            self.state.updated_at = datetime.now(UTC).isoformat()
        return msg

    @property
    def token_count(self) -> int:
        return sum(m.token_estimate() for m in self.messages)

    @property
    def last_user_message(self) -> Message | None:
        for m in reversed(self.messages):
            if m.role == "user":
                return m
        return None

    @property
    def last_assistant_message(self) -> Message | None:
        for m in reversed(self.messages):
            if m.role == "assistant":
                return m
        return None
