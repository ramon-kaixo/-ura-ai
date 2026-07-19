"""LanguageDetector — detecta idioma del mensaje del usuario."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LanguageResult:
    code: str
    name: str
    confidence: float


_SPANISH_LEXICON = frozenset({
    "el", "la", "los", "las", "un", "una", "y", "e", "o", "u",
    "de", "del", "en", "con", "por", "para", "a", "ante", "bajo",
    "es", "son", "fue", "era", "está", "este", "esta", "que",
    "como", "más", "pero", "lo", "le", "se", "no", "me", "te",
    "hola", "adiós", "gracias", "por favor", "qué", "quién",
    "cuándo", "dónde", "cómo", "cuál", "mío", "tu", "su",
    "todo", "nada", "algo", "cada", "muy", "bien", "mal",
})

_ENGLISH_LEXICON = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at",
    "to", "for", "of", "with", "by", "from", "is", "are", "was",
    "were", "be", "been", "have", "has", "had", "do", "does",
    "did", "will", "would", "could", "should", "may", "might",
    "hello", "hi", "goodbye", "thanks", "thank", "please",
    "what", "who", "when", "where", "why", "how", "which",
    "my", "your", "his", "her", "its", "our", "their",
    "all", "nothing", "something", "every", "very", "well",
})


class LanguageDetector:
    def detect(self, text: str) -> LanguageResult:
        if not text.strip():
            return LanguageResult(code="es", name="español", confidence=1.0)

        words = text.lower().split()
        if not words:
            return LanguageResult(code="es", name="español", confidence=1.0)

        es_count = sum(1 for w in words if w in _SPANISH_LEXICON)
        en_count = sum(1 for w in words if w in _ENGLISH_LEXICON)

        total = max(len(words), 1)
        es_ratio = es_count / total
        en_ratio = en_count / total

        if es_ratio > en_ratio and es_ratio > 0.15:
            return LanguageResult(code="es", name="español", confidence=es_ratio)
        if en_ratio > 0.15:
            return LanguageResult(code="en", name="english", confidence=en_ratio)

        return LanguageResult(code="es", name="español", confidence=0.5)
