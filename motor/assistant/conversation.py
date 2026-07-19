"""ConversationEngine — core conversational loop."""
from __future__ import annotations

import re
import threading
import uuid
from typing import Any

from motor.assistant.context_window import ContextWindow
from motor.assistant.intent import IntentEngine
from motor.assistant.message_store import MessageStore
from motor.assistant.models import (
    Conversation,
    ConversationMode,
    ConversationState,
    Message,
    MessageRole,
    UserIntent,
)

_MAX_ACTIVE_CONVERSATIONS = 1000

_REFERENCE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\beso\b"), ""),
    (re.compile(r"\bel\s+anterior\b"), ""),
    (re.compile(r"\blo\s+mismo\b"), ""),
    (re.compile(r"\bhazlo\b"), "ejecuta"),
    (re.compile(r"\bcomo\s+antes\b"), ""),
    (re.compile(r"\bde\s+nuevo\b"), ""),
]


class ConversationEngine:
    def __init__(
        self,
        message_store: MessageStore | None = None,
        context_window: ContextWindow | None = None,
        intent_engine: IntentEngine | None = None,
        max_turns: int = 200,
    ):
        self._store = message_store or MessageStore()
        self._context = context_window or ContextWindow()
        self._intent = intent_engine or IntentEngine()
        self._max_turns = max_turns
        self._active: dict[str, Conversation] = {}
        self._lock = threading.Lock()

    def create_conversation(
        self,
        conversation_id: str = "",
        mode: ConversationMode = ConversationMode.CONVERSATION,
        goal: str = "",
    ) -> Conversation:
        cid = conversation_id or uuid.uuid4().hex[:12]
        conv = Conversation(
            conversation_id=cid,
            state=ConversationState(conversation_id=cid, mode=mode, active_goal=goal),
        )
        with self._lock:
            self._active[cid] = conv
            self._evict_if_needed()
        return conv

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            if conversation_id in self._active:
                return self._active[conversation_id]
            messages = self._store.get_conversation(conversation_id, limit=self._max_turns)
            if not messages:
                return None
            conv = Conversation(conversation_id=conversation_id, messages=messages)
            conv.state = ConversationState(conversation_id=conversation_id)
            self._active[conversation_id] = conv
            self._evict_if_needed()
            return conv

    def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        **kwargs: Any,
    ) -> Message:
        if content is None:
            raise ValueError("message content cannot be None")
        conv = self.get_or_create(conversation_id)
        if conv.state and conv.state.turn_count >= self._max_turns:
            raise RuntimeError(f"Conversation {conversation_id} exceeded max turns ({self._max_turns})")
        msg = conv.add_message(role=role, content=content, **kwargs)
        self._store.append(conversation_id, msg)
        return msg

    def get_context(self, conversation_id: str, system_prompt: str = "") -> list[Message]:
        conv = self.get_or_create(conversation_id)
        return self._context.build_context(conv.messages, system_prompt)

    def detect_intent(self, text: str) -> UserIntent:
        return self._intent.classify(text).intent

    def resolve_reference(self, text: str, conversation_id: str) -> str:
        conv = self.get_or_create(conversation_id)
        resolved = text.lower()
        for pattern, replacement in _REFERENCE_PATTERNS:
            if pattern.search(resolved):
                last = conv.last_user_message
                if last:
                    ctx = last.content[:80].lower()
                    if replacement:
                        resolved = pattern.sub(replacement, resolved)
                    else:
                        resolved = pattern.sub(f"({ctx}...)", resolved)
        return resolved

    def get_or_create(self, conversation_id: str) -> Conversation:
        with self._lock:
            conv = self._active.get(conversation_id)
            if conv is not None:
                return conv
            messages = self._store.get_conversation(conversation_id, limit=self._max_turns)
            if messages:
                conv = Conversation(conversation_id=conversation_id, messages=messages)
                conv.state = ConversationState(conversation_id=conversation_id)
                self._active[conversation_id] = conv
                self._evict_if_needed()
                return conv
            conv = Conversation(
                conversation_id=conversation_id,
                state=ConversationState(conversation_id=conversation_id),
            )
            self._active[conversation_id] = conv
            self._evict_if_needed()
            return conv

    def _evict_if_needed(self) -> None:
        if len(self._active) > _MAX_ACTIVE_CONVERSATIONS:
            excess = len(self._active) - _MAX_ACTIVE_CONVERSATIONS
            for key in list(self._active.keys())[:excess]:
                del self._active[key]

    def list_conversations(self) -> list[dict[str, Any]]:
        return self._store.list_conversations()

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._lock:
            self._active.pop(conversation_id, None)
        return self._store.delete_conversation(conversation_id)
