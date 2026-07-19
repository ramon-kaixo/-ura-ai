"""IntentEngine — comprensión de intención, extracción de entidades y routing."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from motor.assistant.models import UserIntent


@dataclass
class IntentResult:
    intent: UserIntent
    confidence: float
    entities: dict[str, str] = field(default_factory=dict)
    original_text: str = ""
    resolved_text: str = ""


_INTENT_PATTERNS: list[tuple[UserIntent, list[re.Pattern[str]], float]] = [
    (
        UserIntent.GREETING,
        [re.compile(p) for p in [
            r"^(hola|buen[oa]s?\s*(d[ií]as|tardes)|hey|hello|hi|buenas|qu[eé] hay)$",
        ]],
        0.95,
    ),
    (
        UserIntent.FAREWELL,
        [re.compile(p) for p in [
            r"^(adi[oó]s|chao|hasta\s*(luego|pronto|otra)|bye|gracias|thanks|nos\s*vemos)$",
        ]],
        0.95,
    ),
    (
        UserIntent.CONFIRM,
        [re.compile(p) for p in [
            r"^(s[ií]|si|ok|vale|de\s*acuerdo|yes|confirmo|adelante|d[áa]le)$",
        ]],
        0.9,
    ),
    (
        UserIntent.REJECT,
        [re.compile(p) for p in [
            r"^(no|nop|nope|no\s*me\s*gusta|no\s*es\s*eso|cancelar|para)$",
        ]],
        0.9,
    ),
    (
        UserIntent.REPEAT,
        [re.compile(p) for p in [
            r"^(repite|otra\s*vez|no\s*entend[ií]|puedes\s*repetir|rep[eé]telo)$",
        ]],
        0.9,
    ),
    (
        UserIntent.CORRECT,
        [re.compile(p) for p in [
            r"^(corrige|no\s*es\s*correcto|en\s*realidad|mejor\s*d[ií]|rectifica)",
        ]],
        0.85,
    ),
    (
        UserIntent.QUESTION,
        [re.compile(p) for p in [
            r"^(aclara|explica|qu[eé]\s*es|c[oó]mo\s*funciona|por\s*qu[eé]|cu[aá]ndo|d[oó]nde|qui[eé]n)",
            r"^.*\?$",
        ]],
        0.8,
    ),
    (
        UserIntent.COMMAND,
        [re.compile(p) for p in [
            r"^(busca|crea|haz|ejecuta|muestra|lista|navega|abre|cierra|corre|lanza|genera)",
        ]],
        0.85,
    ),
]


_ENTITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("search_query", re.compile(r"(?:busca|search)\s*(?:sobre|de|acerca de)?\s*['\"]?(.+?)['\"]?(?:\s|$|\.)")),
    ("filename", re.compile(r"(?:archivo?|file|documento)\s*['\"]?(.+?)['\"]?(?:\s|$|\.)")),
    ("url", re.compile(r"(https?://[^\s]+)")),
    ("email", re.compile(r"([\w.+-]+@[\w-]+\.[\w.-]+)")),
    ("number", re.compile(r"\b(\d+)\b")),
    ("language", re.compile(r"(?:en|ingl[eé]s|spanish|espa[nñ]ol|catal[aá]n|euskera|franc[eé]s)")),
    ("date", re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")),
    ("path", re.compile(r"(?:ruta|path|directorio)\s*['\"]?(.+?)['\"]?(?:\s|$|\.)")),
]


class IntentEngine:
    def __init__(self):
        self._intent_patterns = _INTENT_PATTERNS
        self._entity_patterns = _ENTITY_PATTERNS

    def classify(self, text: str) -> IntentResult:
        text = text.strip()
        if not text:
            return IntentResult(intent=UserIntent.UNKNOWN, confidence=0.0, original_text=text)

        t = text.lower().strip()

        best_intent = UserIntent.CHAT
        best_confidence = 0.5

        for intent, patterns, confidence in self._intent_patterns:
            for pattern in patterns:
                if pattern.search(t):
                    if confidence > best_confidence:
                        best_intent = intent
                        best_confidence = confidence
                    break

        entities = self._extract_entities(text)
        resolved = self._resolve_references(text)

        return IntentResult(
            intent=best_intent,
            confidence=best_confidence,
            entities=entities,
            original_text=text,
            resolved_text=resolved,
        )

    def _extract_entities(self, text: str) -> dict[str, str]:
        entities: dict[str, str] = {}
        for name, pattern in self._entity_patterns:
            match = pattern.search(text)
            if match:
                try:
                    entities[name] = match.group(1).strip()
                except IndexError:
                    entities[name] = match.group(0).strip()
        return entities

    def _resolve_references(self, text: str) -> str:
        resolved = text
        references = {
            r"\beso\b": "",
            r"\bel anterior\b": "",
            r"\blo mismo\b": "",
            r"\bhazlo\b": "ejecuta",
            r"\bcomo antes\b": "",
            r"\bde nuevo\b": "",
        }
        for ref, replacement in references.items():
            if re.search(ref, resolved.lower()):
                resolved = re.sub(ref, replacement, resolved.lower(), count=1)
        return resolved

    def intent_to_capability(self, intent: UserIntent) -> str:
        mapping = {
            UserIntent.COMMAND: "tools_execute",
            UserIntent.QUESTION: "knowledge_query",
            UserIntent.SEARCH: "web_search",
            UserIntent.CHAT: "conversation",
            UserIntent.CLARIFY: "conversation",
            UserIntent.GREETING: "conversation",
            UserIntent.FAREWELL: "conversation",
            UserIntent.CONFIRM: "conversation",
            UserIntent.REJECT: "conversation",
            UserIntent.CORRECT: "conversation",
            UserIntent.REPEAT: "conversation",
        }
        return mapping.get(intent, "conversation")

    def extract_action_and_target(self, text: str) -> tuple[str, str]:
        action = ""
        target = ""
        cmd_match = re.match(
            r"(busca|crea|haz|ejecuta|muestra|lista|navega|abre|cierra|corre|lanza|genera|elimina|borra|modifica|cambia)\s+(.+)",
            text.strip().lower(),
        )
        if cmd_match:
            action = cmd_match.group(1)
            target = cmd_match.group(2).strip()
        return action, target


class IntentRouter:
    def __init__(self, engine: IntentEngine | None = None):
        self._engine = engine or IntentEngine()

    def route(self, text: str) -> IntentResult:
        result = self._engine.classify(text)
        result.entities["capability"] = self._engine.intent_to_capability(result.intent)
        return result
