"""StyleEngine — estilo conversacional adaptativo según modo e intención."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from motor.assistant.models import ConversationMode, UserIntent


class Tone(Enum):
    CASUAL = "casual"
    NEUTRAL = "neutral"
    PROFESSIONAL = "professional"
    DIDACTIC = "didactic"


class Formality(Enum):
    INFORMAL = "informal"
    NEUTRAL = "neutral"
    FORMAL = "formal"


@dataclass
class StyleProfile:
    tone: Tone = Tone.NEUTRAL
    formality: Formality = Formality.NEUTRAL
    max_length_chars: int = 1000
    use_bullets: bool = False
    use_examples: bool = False
    use_code: bool = False
    depth: str = "normal"  # shallow, normal, deep
    emoji_allowed: bool = True
    system_prompt_suffix: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


_MODE_PROFILES: dict[ConversationMode, StyleProfile] = {
    ConversationMode.CONVERSATION: StyleProfile(
        tone=Tone.CASUAL,
        formality=Formality.INFORMAL,
        max_length_chars=500,
        use_bullets=False,
        use_examples=False,
        depth="shallow",
        emoji_allowed=True,
        system_prompt_suffix="Responde de forma natural y conversacional, como un amigo.",
    ),
    ConversationMode.WORK: StyleProfile(
        tone=Tone.PROFESSIONAL,
        formality=Formality.FORMAL,
        max_length_chars=1500,
        use_bullets=True,
        use_examples=False,
        depth="normal",
        emoji_allowed=False,
        system_prompt_suffix="Responde de forma precisa y estructurada. Usa bullet points cuando sea apropiado.",
    ),
    ConversationMode.EXPLANATION: StyleProfile(
        tone=Tone.DIDACTIC,
        formality=Formality.NEUTRAL,
        max_length_chars=2000,
        use_bullets=True,
        use_examples=True,
        use_code=True,
        depth="deep",
        emoji_allowed=False,
        system_prompt_suffix="Explica paso a paso, como si enseñaras a alguien. Incluye ejemplos concretos.",
    ),
}


_INTENT_OVERRIDES: dict[UserIntent, dict[str, object]] = {
    UserIntent.GREETING: {"max_length_chars": 200, "depth": "shallow"},
    UserIntent.FAREWELL: {"max_length_chars": 150, "depth": "shallow"},
    UserIntent.CONFIRM: {"max_length_chars": 200, "depth": "shallow"},
    UserIntent.REJECT: {"max_length_chars": 200, "depth": "shallow"},
    UserIntent.REPEAT: {"max_length_chars": 800, "depth": "shallow"},
    UserIntent.COMMAND: {"use_bullets": True, "max_length_chars": 1000},
    UserIntent.QUESTION: {"depth": "deep", "use_examples": True},
}


class StyleEngine:
    def __init__(self) -> None:
        self._mode_profiles = _MODE_PROFILES

    def get_profile(self, mode: ConversationMode, intent: UserIntent = UserIntent.CHAT) -> StyleProfile:
        profile = self._mode_profiles.get(mode, _MODE_PROFILES[ConversationMode.CONVERSATION])
        overrides = _INTENT_OVERRIDES.get(intent, {})
        if not overrides:
            return profile

        kwargs: dict[str, Any] = {
            "tone": profile.tone,
            "formality": profile.formality,
            "max_length_chars": profile.max_length_chars,
            "use_bullets": profile.use_bullets,
            "use_examples": profile.use_examples,
            "depth": profile.depth,
        }
        for key, value in overrides.items():
            if key in kwargs:
                kwargs[key] = value
        overridden = StyleProfile(**kwargs)
        overridden.system_prompt_suffix = profile.system_prompt_suffix
        overridden.emoji_allowed = profile.emoji_allowed
        return overridden

    def build_system_prompt(self, mode: ConversationMode, intent: UserIntent = UserIntent.CHAT) -> str:
        profile = self.get_profile(mode, intent)
        parts = [
            profile.system_prompt_suffix,
        ]
        if profile.use_bullets:
            parts.append("Organiza la información en bullet points cuando sea relevante.")
        if profile.use_examples:
            parts.append("Incluye ejemplos concretos para ilustrar los conceptos.")
        if profile.depth == "deep":
            parts.append("Explica en profundidad, cubriendo causas, mecanismos y consecuencias.")
        elif profile.depth == "shallow":
            parts.append("Responde de forma breve y directa.")

        return " ".join(parts)
