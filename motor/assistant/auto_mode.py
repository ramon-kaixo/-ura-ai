"""AutoModeDetector — detecta automáticamente el modo conversacional (F29.5 B2).

Analiza la intención y el contexto para elegir entre:
- conversacion: respuestas concisas por defecto
- explicacion: cuando el usuario pide profundidad
- trabajo: cuando el usuario pide acción/precisión
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from motor.assistant.models import ConversationMode, UserIntent

_EXPLAIN_TRIGGERS = re.compile(
    r"^(expl[ií]came|por\s*qu[eé]|c[oó]mo\s*funciona|qu[eé]\s*es|"
    r"cu[eé]ntame|deta|profundiza|desarrolla|ampl[ií]a|"
    r"a ver|no\s*entiendo|no\s*me\s*queda\s*claro|"
    r"m[eé]s\s*deta|en\s*qu[eé]\s*consiste)",
    re.IGNORECASE,
)

_CONCISE_TRIGGERS = re.compile(
    r"^(resume|concreta|en\s*resumen|breve|corto|directo|"
    r"al\s*grano|no\s*hace\s*falta\s*que\s*expliques|"
    r"solo\s*la\s*respuesta|v[aá]lgame)",
    re.IGNORECASE,
)

_WORK_TRIGGERS = re.compile(
    r"^(haz|ejecuta|busca|crea|modifica|elimina|"
    r"muestra|lista|navega|corre|lanza|genera|status|log)",
    re.IGNORECASE,
)


@dataclass
class AutoModeResult:
    mode: ConversationMode
    confidence: float
    reason: str = ""
    triggers: list[str] = field(default_factory=list)


class AutoModeDetector:
    def __init__(self) -> None:
        self._current_mode: dict[str, ConversationMode] = {}

    def detect_mode(
        self,
        user_message: str,
        intent: UserIntent,
        previous_mode: ConversationMode | None = None,
        conversation_id: str = "",
    ) -> AutoModeResult:
        if intent == UserIntent.COMMAND:
            return AutoModeResult(
                mode=ConversationMode.WORK,
                confidence=0.95,
                reason="comando detectado",
                triggers=["intent=COMMAND"],
            )

        explain = _EXPLAIN_TRIGGERS.search(user_message)
        if explain:
            return AutoModeResult(
                mode=ConversationMode.EXPLANATION,
                confidence=0.9,
                reason="solicitud de explicación",
                triggers=[explain.group(0)],
            )

        concise = _CONCISE_TRIGGERS.search(user_message)
        if concise:
            return AutoModeResult(
                mode=ConversationMode.CONVERSATION,
                confidence=0.85,
                reason="solicitud de concisión",
                triggers=[concise.group(0)],
            )

        work = _WORK_TRIGGERS.search(user_message)
        if work:
            return AutoModeResult(
                mode=ConversationMode.WORK,
                confidence=0.8,
                reason="acción detectada",
                triggers=[work.group(0)],
            )

        if previous_mode:
            return AutoModeResult(
                mode=previous_mode,
                confidence=0.7,
                reason="manteniendo modo anterior",
            )

        return AutoModeResult(
            mode=ConversationMode.CONVERSATION,
            confidence=0.6,
            reason="modo por defecto: conversación natural",
        )

    def set_mode(self, conversation_id: str, mode: ConversationMode) -> None:
        self._current_mode[conversation_id] = mode

    def get_mode(self, conversation_id: str) -> ConversationMode | None:
        return self._current_mode.get(conversation_id)
