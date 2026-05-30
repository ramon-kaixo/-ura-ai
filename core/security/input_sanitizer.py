"""
Módulo: core/security/input_sanitizer.py
Propósito: Sanitiza y valida entradas de usuario para prevenir inyección y overflow.
Dependencias principales: re, html, logging
Reglas especiales: Aplicar siempre antes de procesar input. Limitar longitud máxima.
"""

import re
import html
import logging

logger = logging.getLogger(__name__)


class InputSanitizer:
    def __init__(self, max_length: int = 5000):
        self.max_length = max_length
        self.allowed_tags = []
        self.dangerous_patterns = [
            r"<script.*?>.*?</script>",
            r"javascript\s*:",
            r"on\w+\s*=",
            r"<iframe",
            r"<embed",
            r"<object",
            r"data\s*:",
            r"vbscript\s*:",
            r'<link.*?rel\s*=\s*["\']stylesheet["\']',
            r"<meta.*?http-equiv",
            r"eval\s*\(",
            r"document\.cookie",
            r"document\.write",
            r"window\.location",
            r"alert\s*\(",
            r"prompt\s*\(",
            r"confirm\s*\(",
        ]
        self.compiled_patterns = [
            re.compile(p, re.IGNORECASE | re.DOTALL) for p in self.dangerous_patterns
        ]

    def sanitize(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        text = text[: self.max_length]
        text = html.escape(text)
        return text

    def is_dangerous(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                logger.warning(f"Patrón peligroso detectado en input: {pattern.pattern}")
                return True
        return False

    def clean(self, text: str) -> str:
        if self.is_dangerous(text):
            logger.warning(f"Input bloqueado por InputSanitizer: {text[:100]}...")
            return "[BLOQUEADO por InputSanitizer]"
        return text


# Singleton
_input_sanitizer: InputSanitizer | None = None


def get_input_sanitizer() -> InputSanitizer:
    """Obtener el singleton del input sanitizer."""
    global _input_sanitizer
    if _input_sanitizer is None:
        _input_sanitizer = InputSanitizer()
    return _input_sanitizer


def sanitize_user_input(text: str) -> str:
    """Función conveniente para sanitizar input de usuario."""
    return get_input_sanitizer().clean(text)
