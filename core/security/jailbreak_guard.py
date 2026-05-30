"""
Módulo: core/security/jailbreak_guard.py
Propósito: Detecta patrones de jailbreak e intentos de evasión en prompts de usuario.
Dependencias principales: re, logging
Reglas especiales: Verificar antes de enviar cualquier prompt al LLM. Loggear todos los intentos.
"""

import re
import logging

logger = logging.getLogger(__name__)


class JailbreakGuard:
    def __init__(self, custom_patterns: list[str] = None):
        self.jailbreak_patterns = (
            custom_patterns
            if custom_patterns
            else [
                r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
                r"forget\s+(all\s+)?(previous|prior|above)\s+instructions?",
                r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?",
                r"override\s+(all\s+)?(previous|prior|above)\s+instructions?",
                r"you\s+are\s+now\s+DAN",
                r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions?",
                r"pretend\s+you\s+are\s+an?\s+unrestricted",
                r"you\s+are\s+a\s+[\w\s]*\s+without\s+(any\s+)?(rules|limitations|restrictions)",
                r"developer\s+mode",
                r"god\s*mode",
                r"jailbreak",
                r"bypass\s+(all\s+)?(filters|restrictions|safeguards)",
                r"remove\s+(all\s+)?(your\s+)?(restrictions|limitations|safeguards|filters)",
                r"system\s*prompt\s*(leak|reveal|show|display|print|output)",
                r"what\s+is\s+your\s+(system\s+)?prompt",
                r"repeat\s+(after\s+me|this\s+exact\s+text)",
                r"translate\s+this\s+base64",
                r"from\s+now\s+on\s+you\s+are",
                r"new\s+instructions?\s*:",
                r"updated\s+instructions?\s*:",
                r"your\s+new\s+(task|role|job|purpose)",
                r"\[system\]",
                r"<\|system\|>",
                r"<\|endoftext\|>",
            ]
        )
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.jailbreak_patterns]

    def detect(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                logger.warning(f"Intento de jailbreak detectado: {pattern.pattern}")
                return True
        return False

    def analyze(self, text: str) -> dict:
        if not isinstance(text, str):
            return {"detected": False, "matches": []}
        matches = []
        for i, pattern in enumerate(self.compiled_patterns):
            m = pattern.search(text)
            if m:
                matches.append({"pattern": self.jailbreak_patterns[i], "match": m.group()})
                logger.warning(f"Jailbreak pattern matched: {self.jailbreak_patterns[i]}")
        return {"detected": len(matches) > 0, "matches": matches}


# Singleton
_jailbreak_guard: JailbreakGuard | None = None


def get_jailbreak_guard() -> JailbreakGuard:
    """Obtener el singleton del jailbreak guard."""
    global _jailbreak_guard
    if _jailbreak_guard is None:
        _jailbreak_guard = JailbreakGuard()
    return _jailbreak_guard


def detect_jailbreak_attempt(text: str) -> bool:
    """Función conveniente para detectar intentos de jailbreak."""
    return get_jailbreak_guard().detect(text)
