"""ConversationEngine — core conversational loop."""
from __future__ import annotations

import re
import threading
import uuid
from typing import Any

from motor.assistant.auto_mode import AutoModeDetector
from motor.assistant.context_window import ContextWindow
from motor.assistant.episodic_memory import EpisodicConversationMemory
from motor.assistant.intent import IntentEngine
from motor.assistant.interruption import InterruptionSystem
from motor.assistant.message_store import MessageStore
from motor.assistant.models import (
    Conversation,
    ConversationMode,
    ConversationState,
    Message,
    MessageRole,
    UserIntent,
)
from motor.assistant.trends import TrendAwareness

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
        auto_mode: AutoModeDetector | None = None,
        interruption_system: InterruptionSystem | None = None,
        episodic_memory: EpisodicConversationMemory | None = None,
        trend_awareness: TrendAwareness | None = None,
        max_turns: int = 200,
    ):
        store = message_store or MessageStore()
        self._store = store
        self._context = context_window or ContextWindow()
        self._intent = intent_engine or IntentEngine()
        self._auto_mode = auto_mode or AutoModeDetector()
        self._interruptions = interruption_system or InterruptionSystem()
        self._episodic = episodic_memory or EpisodicConversationMemory(message_store=store)
        self._trends = trend_awareness or TrendAwareness()
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

    def process_user_message(
        self,
        conversation_id: str,
        user_message: str,
    ) -> dict[str, object]:
        intent = self.detect_intent(user_message)
        conv = self.get_or_create(conversation_id)

        is_interruption = self._interruptions.detect_interruption(
            conversation_id, conv.messages,
        )

        mode_result = self._auto_mode.detect_mode(
            user_message, intent,
            previous_mode=conv.state.mode if conv.state else None,
            conversation_id=conversation_id,
        )
        if conv.state:
            conv.state.mode = mode_result.mode
            self._auto_mode.set_mode(conversation_id, mode_result.mode)

        resolved = self.resolve_reference(user_message, conversation_id)

        interruption_context = ""
        if is_interruption:
            interruption_context = self._interruptions.auto_recover_context(
                conversation_id, mode_result.mode.value,
            )

        episodic_context = self._episodic.get_relevant_context(user_message)

        trend = self._trends.analyze_query(user_message, intent.value)
        needs_web = trend.needs_update

        return {
            "intent": intent,
            "mode": mode_result.mode,
            "mode_reason": mode_result.reason,
            "resolved_message": resolved,
            "is_interruption": is_interruption,
            "interruption_context": interruption_context,
            "episodic_context": episodic_context,
            "needs_web_search": needs_web,
            "trend_reason": trend.reason,
        }

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
