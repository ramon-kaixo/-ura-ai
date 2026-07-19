"""TrendAwareness — conocimiento de tendencias y novedades (F29.5 B4).

Analiza consultas del usuario y detecta si necesita información actualizada
(no cubierta por el conocimiento estático). Opcional: se apoya en web_search.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

_KNOWLEDGE_CUTOFF = datetime(2026, 7, 19, tzinfo=UTC)

_TEMPORAL_TRIGGERS = re.compile(
    r"\b(actualmente|hoy|ahora|últimamente|nuevo|tendencia|"
    r"reciente|de moda|202[4-9]|futuro|próximamente|"
    r"latest|news|breaking|upcoming|current)\b",
    re.IGNORECASE,
)


@dataclass
class TrendResult:
    needs_update: bool
    confidence: float
    reason: str = ""
    suggested_sources: list[str] = field(default_factory=list)


class TrendAwareness:
    def __init__(self, knowledge_cutoff: datetime | None = None):
        self._cutoff = knowledge_cutoff or _KNOWLEDGE_CUTOFF

    def analyze_query(self, user_message: str, intent: str = "") -> TrendResult:
        has_temporal = bool(_TEMPORAL_TRIGGERS.search(user_message))
        is_question = intent in {"question", "search"}

        if has_temporal and is_question:
            return TrendResult(
                needs_update=True,
                confidence=0.85,
                reason="consulta sobre situación actual detectada",
                suggested_sources=["web_search", "news_api"],
            )

        if has_temporal:
            return TrendResult(
                needs_update=True,
                confidence=0.6,
                reason="menciona tiempo actual sin ser pregunta directa",
            )

        return TrendResult(
            needs_update=False,
            confidence=0.5,
            reason="sin indicios de necesidad de información actualizada",
        )

    def needs_web_search(self, user_message: str) -> bool:
        return bool(_TEMPORAL_TRIGGERS.search(user_message))
