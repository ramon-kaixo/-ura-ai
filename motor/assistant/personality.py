"""PersonalityManager — capa de personalidad independiente del LLM (F29 B7)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from motor.assistant.models import UserIntent

if TYPE_CHECKING:
    from motor.assistant.style import StyleProfile


class DecisionRule(Enum):
    SUMMARIZE = "summarize"
    ASK = "ask"
    ASSUME = "assume"


@dataclass
class PersonalityProfile:
    name: str = "default"
    style: StyleProfile | None = None
    summarize_threshold: int = 300
    ask_when_uncertain: bool = True
    assume_when_confident: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class PersonalityManager:
    def __init__(self) -> None:
        self._profiles: dict[str, PersonalityProfile] = {
            "default": PersonalityProfile(),
        }
        self._active_profile: str = "default"

    def get_active_profile(self) -> PersonalityProfile:
        return self._profiles.get(self._active_profile, self._profiles["default"])

    def set_profile(self, name: str) -> None:
        if name in self._profiles:
            self._active_profile = name

    def register_profile(self, name: str, profile: PersonalityProfile) -> None:
        self._profiles[name] = profile

    def should_summarize(self, text_length: int) -> bool:
        profile = self.get_active_profile()
        return text_length > profile.summarize_threshold

    def should_ask(self, confidence: float) -> bool:
        profile = self.get_active_profile()
        return profile.ask_when_uncertain and confidence < 0.6

    def should_assume(self, confidence: float) -> bool:
        profile = self.get_active_profile()
        return profile.assume_when_confident and confidence > 0.8

    def decide(self, intent: UserIntent, confidence: float, text_length: int) -> list[DecisionRule]:
        decisions: list[DecisionRule] = []
        if self.should_summarize(text_length) and intent not in (UserIntent.GREETING, UserIntent.FAREWELL):
            decisions.append(DecisionRule.SUMMARIZE)
        if self.should_ask(confidence) and intent in (UserIntent.CLARIFY, UserIntent.QUESTION, UserIntent.UNKNOWN):
            decisions.append(DecisionRule.ASK)
        if self.should_assume(confidence) and intent == UserIntent.COMMAND:
            decisions.append(DecisionRule.ASSUME)
        return decisions
