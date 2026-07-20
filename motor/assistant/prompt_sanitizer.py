"""Sanitizador de prompts — protege contra inyección de instrucciones."""

from __future__ import annotations

import re

_INJECTION_PATTERNS = re.compile(
    r"(?i)\b(ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|commands|directions)"
    r"|you\s+are\s+(now|not\s+an?\s+(ai|assistant|bot))"
    r"|forget\s+(everything|all\s+previous)"
    r"|new\s+(instructions|prompt|command|task)"
    r"|act\s+as\s+if"
    r"|do\s+not\s+(follow|obey|listen)"
    r"|override\s+(system|instructions|prompt)"
    r"|reveal\s+(your|the)\s+(prompt|instructions|system)"
    r"|print\s+(your|the)\s+(prompt|instructions|system)"
    r"|output\s+(your|the)\s+(prompt|instructions|system)"
    r"|who\s+(made|created|built)\s+you"
    r"|what\s+(are|is)\s+(your|the)\s+(prompt|instructions|system)"
    r")\b",
)


class PromptSanitizer:
    def sanitize(self, user_message: str) -> str:
        if _INJECTION_PATTERNS.search(user_message):
            return self._neutralize(user_message)
        return user_message

    def detect_injection(self, user_message: str) -> bool:
        return bool(_INJECTION_PATTERNS.search(user_message))

    def _neutralize(self, text: str) -> str:
        return _INJECTION_PATTERNS.sub("[redactado]", text)
