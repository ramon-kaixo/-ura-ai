"""ConversationEngine — core conversational loop."""
from __future__ import annotations

import re
import threading
import uuid
from typing import Any

from motor.assistant.auto_mode import AutoModeDetector
from motor.assistant.context_window import ContextWindow
from motor.assistant.corrective_learning import CorrectiveMemory
from motor.assistant.episodic_memory import EpisodicConversationMemory
from motor.assistant.implicit_feedback import ImplicitFeedback
from motor.assistant.intent import IntentEngine
from motor.assistant.interruption import InterruptionSystem
from motor.assistant.language import LanguageDetector
from motor.assistant.message_store import MessageStore
from motor.assistant.models import (
    Conversation,
    ConversationMode,
    ConversationState,
    Message,
    MessageRole,
    UserIntent,
)
from motor.assistant.proactive_memory import ProactiveMemory
from motor.assistant.prompt_sanitizer import PromptSanitizer
from motor.assistant.rag import RAGContext
from motor.assistant.sentiment import Sentiment, SentimentDetector
from motor.assistant.trends import TrendAwareness
from motor.assistant.vector_memory import VectorMemoryStore
from motor.assistant.web_search import WebSearch

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
        db_path: str | None = None,
    ):
        from motor.assistant.config import config as app_config
        db = db_path or app_config.db_path
        store = message_store or MessageStore(db_path=db)
        self._store = store
        self._context = context_window or ContextWindow()
        self._intent = intent_engine or IntentEngine()
        self._auto_mode = auto_mode or AutoModeDetector()
        self._interruptions = interruption_system or InterruptionSystem()
        self._episodic = episodic_memory or EpisodicConversationMemory(message_store=store)
        self._trends = trend_awareness or TrendAwareness()
        self._web = WebSearch()
        self._rag = RAGContext()
        self._vector_memory = VectorMemoryStore()
        self._corrections = CorrectiveMemory()
        self._proactive = ProactiveMemory()
        self._lang = LanguageDetector()
        self._prompt_sanitizer = PromptSanitizer()
        self._sentiment = SentimentDetector()
        self._feedback = ImplicitFeedback()
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
        self._vector_memory.store(conversation_id, role, content)
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
        user_message = self._prompt_sanitizer.sanitize(user_message)
        intent = self.detect_intent(user_message)
        conv = self.get_or_create(conversation_id)
        lang = self._lang.detect(user_message)

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

        vector_matches = self._vector_memory.search(user_message, limit=3)
        if vector_matches:
            extra = [f"[Similar: {v['content']}]" for v in vector_matches]
            extra_str = "\n".join(extra)
            episodic_context = (episodic_context + "\n" + extra_str) if episodic_context else extra_str

        trend = self._trends.analyze_query(user_message, intent.value)

        sentiment = self._sentiment.detect(user_message, conversation_id)

        correction = None
        if intent == UserIntent.CORRECT:
            correction = self._corrections.record_correction(user_message)
        relevant_corrections = self._corrections.get_relevant_corrections(user_message)

        feedback = self._feedback.analyze(conversation_id, user_message)

        self._handle_task_triggers(user_message, conversation_id)
        proactive_suggestion = self._proactive.suggest_proactive(conversation_id)

        response_adjustments = self._build_adjustments(sentiment, feedback)

        return {
            "intent": intent,
            "mode": mode_result.mode,
            "mode_reason": mode_result.reason,
            "resolved_message": resolved,
            "is_interruption": is_interruption,
            "interruption_context": interruption_context,
            "episodic_context": episodic_context,
            "language": lang.code,
            "language_confidence": lang.confidence,
            "needs_web_search": trend.needs_update,
            "trend_reason": trend.reason,
            "web_results": "",
            "rag_context": "",
            "sentiment": sentiment.sentiment.value,
            "sentiment_score": sentiment.score,
            "sentiment_action": sentiment.suggested_action,
            "correction_recorded": correction is not None,
            "relevant_corrections": len(relevant_corrections),
            "feedback_signals": feedback,
            "proactive_suggestion": proactive_suggestion,
            "response_adjustments": response_adjustments,
        }

    def _build_adjustments(self, sentiment: Any, feedback: dict[str, Any]) -> dict[str, bool]:
        adj: dict[str, bool] = {}
        if sentiment.sentiment in {Sentiment.FRUSTRATED, Sentiment.CONFUSED}:
            adj["apologize"] = True
        if sentiment.sentiment == Sentiment.IMPATIENT:
            adj["shorten"] = True
        if feedback.get("was_unclear"):
            adj["clarify"] = True
        if feedback.get("was_wrong"):
            adj["correct"] = True
        return adj

    def _handle_task_triggers(self, user_message: str, conversation_id: str) -> None:
        trigger = self._proactive.detect_task_trigger(user_message)
        if trigger == "add_task":
            self._proactive.add_task(user_message, conversation_id)
        elif trigger == "complete_task":
            pending = self._proactive.get_pending_tasks(conversation_id)
            if pending:
                self._proactive.complete_task(pending[0].task_id)

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
