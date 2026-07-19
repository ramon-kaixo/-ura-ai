"""ConversationManager — gestión de conversaciones (F29 B9).

Detecta cambios de objetivo, divide conversaciones largas,
resume automáticamente, recupera temas antiguos y recuerda tareas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from motor.assistant.message_store import MessageStore
from motor.assistant.models import UserIntent


@dataclass
class ConversationSummary:
    conversation_id: str
    summary: str
    topics: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    created_at: str = ""
    message_count: int = 0

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()


class ConversationManager:
    def __init__(self, message_store: MessageStore | None = None) -> None:
        self._store = message_store or MessageStore()
        self._summaries: dict[str, ConversationSummary] = {}
        self._goals: dict[str, str] = {}

    def detect_goal_change(self, conversation_id: str, current_intent: UserIntent) -> bool:
        old_goal = self._goals.get(conversation_id)
        if old_goal is None:
            return False
        new_goal = self._intent_to_goal(current_intent)
        if old_goal != new_goal:
            self._goals[conversation_id] = new_goal
            return True
        return False

    def set_goal(self, conversation_id: str, intent: UserIntent) -> None:
        self._goals[conversation_id] = self._intent_to_goal(intent)

    def _intent_to_goal(self, intent: UserIntent) -> str:
        mapping = {
            UserIntent.QUESTION: "research",
            UserIntent.COMMAND: "execute",
            UserIntent.CHAT: "chat",
            UserIntent.CLARIFY: "clarify",
            UserIntent.GREETING: "greeting",
            UserIntent.FAREWELL: "farewell",
            UserIntent.CONFIRM: "confirm",
            UserIntent.REJECT: "reject",
            UserIntent.CORRECT: "correct",
            UserIntent.REPEAT: "repeat",
        }
        return mapping.get(intent, "chat")

    def needs_summary(self, conversation_id: str, message_count: int, max_before_summary: int = 50) -> bool:
        return message_count >= max_before_summary and conversation_id not in self._summaries

    def store_summary(self, conversation_id: str, summary: ConversationSummary) -> None:
        self._summaries[conversation_id] = summary

    def get_summary(self, conversation_id: str) -> ConversationSummary | None:
        return self._summaries.get(conversation_id)

    def split_conversation(self, conversation_id: str, split_point: int) -> str:
        messages = self._store.get_conversation(conversation_id)
        if len(messages) <= split_point:
            return conversation_id

        new_id = f"{conversation_id}_part2"
        for msg in messages[split_point:]:
            self._store.append(new_id, msg)
        return new_id

    def add_pending_task(self, conversation_id: str, task: str) -> None:
        summary = self._summaries.get(conversation_id)
        if summary:
            if task not in summary.pending_tasks:
                summary.pending_tasks.append(task)
        else:
            summary = ConversationSummary(
                conversation_id=conversation_id,
                summary="",
                pending_tasks=[task],
            )
            self._summaries[conversation_id] = summary

    def get_pending_tasks(self, conversation_id: str) -> list[str]:
        summary = self._summaries.get(conversation_id)
        return summary.pending_tasks if summary else []
