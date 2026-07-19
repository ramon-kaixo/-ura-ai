"""SentimentDetector — detecta estado emocional del usuario (F29.6 B3).

Detecta frustración, satisfacción, confusión, impaciencia y ajusta
la respuesta del asistente en consecuencia.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Sentiment(Enum):
    NEUTRAL = "neutral"
    SATISFIED = "satisfied"
    FRUSTRATED = "frustrated"
    CONFUSED = "confused"
    IMPATIENT = "impatient"
    GRATEFUL = "grateful"


@dataclass
class SentimentResult:
    sentiment: Sentiment
    confidence: float
    score: float = 0.0
    triggers: list[str] = field(default_factory=list)
    suggested_action: str = ""


_FRUSTRATION_PATTERNS = re.compile(
    r"\b(no me (gusta|convence|sirve|vale)|no es (lo que|correcto|eso)|"
    r"para nada|mal|error|incorrecto|falla|no funciona|"
    r"otra vez no|siempre igual|no aprendes|"
    r"es que no|pero yo te dije|te he dicho)",
    re.IGNORECASE,
)

_SATISFACTION_PATTERNS = re.compile(
    r"\b(perfecto|excelente|genial|estupendo|maravilloso|"
    r"justo lo que|eso es|así|bien hecho|buen trabajo|"
    r"me gusta|me sirve|me vale|exacto|correcto|funciona)",
    re.IGNORECASE,
)

_CONFUSION_PATTERNS = re.compile(
    r"\b(no entiendo|cómo dices|qué significa|no me queda claro|"
    r"puedes explicar|a qué te refieres|no sé|no comprendo|"
    r"huh|eh|perdona)",
    re.IGNORECASE,
)

_IMPATIENCE_PATTERNS = re.compile(
    r"\b(ya está|cuánto falta|cuánto tarda|date prisa|"
    r"vamos|termina ya|suelta ya|al grano|concreta|"
    r"no me enrolles|no te extiendas)",
    re.IGNORECASE,
)

_GRATITUDE_PATTERNS = re.compile(
    r"\b(gracias|thanks|thank you|muy amable|te lo agradezco|"
    r"eres un sol|qué bien|perfecto gracias)",
    re.IGNORECASE,
)


class SentimentDetector:
    def __init__(self) -> None:
        self._history: dict[str, list[SentimentResult]] = {}

    def detect(self, user_message: str, conversation_id: str = "") -> SentimentResult:
        if _FRUSTRATION_PATTERNS.search(user_message):
            result = SentimentResult(
                sentiment=Sentiment.FRUSTRATED,
                confidence=0.85,
                score=-0.6,
                triggers=["frustration_detected"],
                suggested_action="disculparse y ofrecer alternativa",
            )
        elif _IMPATIENCE_PATTERNS.search(user_message):
            result = SentimentResult(
                sentiment=Sentiment.IMPATIENT,
                confidence=0.8,
                score=-0.4,
                triggers=["impatience_detected"],
                suggested_action="acortar respuesta, ir al grano",
            )
        elif _CONFUSION_PATTERNS.search(user_message):
            result = SentimentResult(
                sentiment=Sentiment.CONFUSED,
                confidence=0.8,
                score=-0.3,
                triggers=["confusion_detected"],
                suggested_action="simplificar, preguntar si necesita aclaración",
            )
        elif _SATISFACTION_PATTERNS.search(user_message):
            result = SentimentResult(
                sentiment=Sentiment.SATISFIED,
                confidence=0.85,
                score=0.5,
                triggers=["satisfaction_detected"],
                suggested_action="reforzar, ofrecer más ayuda",
            )
        elif _GRATITUDE_PATTERNS.search(user_message):
            result = SentimentResult(
                sentiment=Sentiment.GRATEFUL,
                confidence=0.9,
                score=0.7,
                triggers=["gratitude_detected"],
                suggested_action="despedida cordial, ofrecer ayuda futura",
            )
        else:
            result = SentimentResult(
                sentiment=Sentiment.NEUTRAL,
                confidence=0.5,
                score=0.0,
                suggested_action="respuesta normal",
            )

        if conversation_id:
            if conversation_id not in self._history:
                self._history[conversation_id] = []
            self._history[conversation_id].append(result)

        return result

    def get_trend(self, conversation_id: str) -> float:
        recent = self._history.get(conversation_id, [])[-5:]
        if not recent:
            return 0.0
        return sum(r.score for r in recent) / len(recent)

    def should_apologize(self, sentiment: Sentiment) -> bool:
        return sentiment in (Sentiment.FRUSTRATED, Sentiment.CONFUSED)

    def should_shorten_response(self, sentiment: Sentiment) -> bool:
        return sentiment == Sentiment.IMPATIENT

    def should_offer_help(self, sentiment: Sentiment) -> bool:
        return sentiment in (Sentiment.SATISFIED, Sentiment.GRATEFUL)
