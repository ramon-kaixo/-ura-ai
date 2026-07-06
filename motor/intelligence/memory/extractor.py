"""FactExtractor — interfaz abstracta para extracción de hechos desde episodios."""

from __future__ import annotations

from abc import ABC, abstractmethod

from motor.intelligence.memory.episodic import Episode  # noqa: TC001
from motor.intelligence.memory.semantic import SemanticFact


class FactExtractor(ABC):
    @abstractmethod
    def extract(self, episode: Episode) -> list[SemanticFact]:
        ...


class RuleBasedFactExtractor(FactExtractor):
    def extract(self, episode: Episode) -> list[SemanticFact]:
        if not episode.payload:
            return []
        facts: list[SemanticFact] = []
        text = episode.payload

        for match in self._find_patterns(text):
            fact = self._make_fact(episode, *match)
            if fact:
                facts.append(fact)

        return facts

    def _make_fact(
        self, episode: Episode, subject: str, predicate: str, object_value: str, fact_type: str,
    ) -> SemanticFact:
        return SemanticFact(
            subject=subject.strip(),
            predicate=predicate.strip(),
            object_value=object_value.strip(),
            fact_type=fact_type,
            source_episode_ids=[episode.id],
            tags=list(episode.tags),
            metadata={"session_id": episode.session_id},
            confidence=episode.confidence * 0.9,
            importance=episode.importance,
        )

    def _find_patterns(self, text: str) -> list[tuple[str, str, str, str]]:
        import re
        results: list[tuple[str, str, str, str]] = []

        patterns = [
            (r"(?:El|La|El sistema)\s+(\w+(?:\s+\w+)?)\s+(?:es|está)\s+(\w+)\s+(.+)", "attribute"),
            (r"(\w+(?:\s+\w+)?)\s+(?:tiene|contiene|incluye|dispone de)\s+(.+)", "relation"),
            (r"(?:el|la)\s+(\w+(?:\s+\w+)?)\s+(?:se|se ha)\s+(\w+)\s+(.+)", "event"),
            (r"(\w+(?:\s+\w+)?)\s+(?:dice|indica|responde|devuelve)\s+(?:que\s+)?(.+)", "statement"),
            (r"Error:\s*(.+)", "error"),
            (r"(?:Configuración|configuración)\s+(\w+)\s*[=:]\s*(.+)", "attribute"),
            (r"(\w+)\s*(?:es|es igual a|=)\s*(\d+\.?\d*)", "attribute"),
        ]

        for pattern, fact_type in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                groups = m.groups()
                if fact_type == "relation":
                    results.append((groups[0], "tiene", groups[1], fact_type))
                elif fact_type == "attribute" and len(groups) >= 2:
                    results.append(("sistema", groups[0], groups[1], fact_type))
                elif fact_type == "event":
                    results.append((groups[0], groups[1], groups[2] if len(groups) > 2 else "", fact_type))
                elif fact_type == "error":
                    results.append(("sistema", "error", groups[0], fact_type))
                elif fact_type == "statement":
                    results.append((groups[0], "dice", groups[1] if len(groups) > 1 else "", fact_type))
                else:
                    results.append((groups[0], "es", groups[1] if len(groups) > 1 else "", fact_type))

        return results
