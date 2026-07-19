"""ConversationEngine — core conversational loop."""

from __future__ import annotations

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
        self._active[cid] = conv
        return conv

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        if conversation_id in self._active:
            return self._active[conversation_id]
        messages = self._store.get_conversation(conversation_id)
        if not messages:
            return None
        conv = Conversation(conversation_id=conversation_id, messages=messages)
        conv.state = ConversationState(conversation_id=conversation_id)
        self._active[conversation_id] = conv
        return conv

    def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        **kwargs: Any,
    ) -> Message:
        conv = self.get_or_create(conversation_id)
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
        resolved = text
        replacements = {
            "eso": "",
            "el anterior": "",
            "lo mismo": "",
            "hazlo": "ejecuta",
        }
        for ref in replacements:
            if ref in resolved.lower():
                last = conv.last_user_message
                if last:
                    resolved = resolved.lower().replace(ref, f"({last.content[:80]}...)")
        return resolved

    def get_or_create(self, conversation_id: str) -> Conversation:
        conv = self.get_conversation(conversation_id)
        if conv is None:
            conv = self.create_conversation(conversation_id)
        return conv

    def list_conversations(self) -> list[dict[str, Any]]:
        return self._store.list_conversations()

    def delete_conversation(self, conversation_id: str) -> bool:
        self._active.pop(conversation_id, None)
        return self._store.delete_conversation(conversation_id)
