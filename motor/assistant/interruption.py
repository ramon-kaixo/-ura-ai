"""InterruptionSystem — manejo de interrupciones en la conversación (F29.5 B1).

Permite que el usuario interrumpa una respuesta del asistente,
preservando el contexto de lo que se estaba diciendo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.assistant.models import Message


@dataclass
class InterruptionContext:
    conversation_id: str
    interrupted_message: str
    interrupted_at: str = ""
    resumed: bool = False
    context_before_interruption: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.interrupted_at:
            self.interrupted_at = datetime.now(UTC).isoformat()


class InterruptionSystem:
    def __init__(self) -> None:
        self._interruptions: dict[str, InterruptionContext] = {}

    def detect_interruption(
        self,
        conversation_id: str,
        messages: list[Message],
    ) -> bool:
        if len(messages) < 2:
            return False
        last = messages[-1]
        second_last = messages[-2]
        is_interruption = (
            last.role == "user"
            and second_last.role == "assistant"
        )
        if is_interruption:
            self._interruptions[conversation_id] = InterruptionContext(
                conversation_id=conversation_id,
                interrupted_message=second_last.content[:200],
                context_before_interruption=[
                    {"role": m.role, "content": m.content[:100]}
                    for m in messages[-6:-2]
                ],
            )
        return is_interruption

    def get_interruption(self, conversation_id: str) -> InterruptionContext | None:
        ctx = self._interruptions.get(conversation_id)
        if ctx and not ctx.resumed:
            return ctx
        return None

    def mark_resumed(self, conversation_id: str) -> None:
        ctx = self._interruptions.get(conversation_id)
        if ctx:
            ctx.resumed = True

    def auto_recover_context(self, conversation_id: str, mode: str = "conversacion") -> str:
        ctx = self.get_interruption(conversation_id)
        if not ctx:
            return ""
        recovered = (
            f"[El usuario interrumpió cuando decías: '{ctx.interrupted_message}'. "
            f"Contexto anterior: {ctx.context_before_interruption[-1:]}. "
            f"Modo: {mode}. Retoma desde donde ibas, más breve.]"
        )
        self.mark_resumed(conversation_id)
        return recovered
