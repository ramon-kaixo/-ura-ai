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

_FRENCH_LEXICON = frozenset({
    "le", "la", "les", "un", "une", "des", "et", "ou", "mais", "donc",
    "de", "du", "en", "avec", "pour", "sur", "dans", "par", "est", "sont",
    "bonjour", "merci", "salut", "au revoir", "s'il vous plaît", "oui", "non",
    "que", "qui", "quoi", "comment", "pourquoi", "quand", "où",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
    "mon", "ton", "son", "ma", "ta", "sa", "mes", "tes", "ses",
    "très", "bien", "mal", "tout", "rien", "quelque", "chaque",
})

_CATALAN_LEXICON = frozenset({
    "el", "la", "els", "les", "un", "una", "uns", "unes", "i", "o", "però",
    "de", "del", "en", "amb", "per", "a", "és", "són", "no", "si",
    "hola", "gràcies", "adeu", "si us plau", "bon dia", "bona tarda",
    "que", "qui", "com", "per què", "quan", "on",
    "jo", "tu", "ell", "ella", "nosaltres", "vosaltres", "ells", "elles",
    "molt", "ben", "tot", "res", "cada", "aquest", "aquesta",
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
        fr_count = sum(1 for w in words if w in _FRENCH_LEXICON)
        ca_count = sum(1 for w in words if w in _CATALAN_LEXICON)

        total = max(len(words), 1)
        es_ratio = es_count / total
        en_ratio = en_count / total
        fr_ratio = fr_count / total
        ca_ratio = ca_count / total

        ratios = [
            (es_ratio, "es", "español"),
            (en_ratio, "en", "english"),
            (fr_ratio, "fr", "français"),
            (ca_ratio, "ca", "català"),
        ]
        best = max(ratios, key=lambda x: x[0])
        if best[0] > 0.15:
            return LanguageResult(code=best[1], name=best[2], confidence=best[0])

        return LanguageResult(code="es", name="español", confidence=0.5)
