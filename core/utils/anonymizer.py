"""anonymizer.py — Saneamiento determinista de datos sensibles.

Patrones adaptados de Trufflehog y Microsoft Presidio.
Sin dependencias externas. Solo re + typing.
"""

from __future__ import annotations

import re

PATTERNS: dict[str, re.Pattern] = {
    "IP_ADDRESS": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
    ),
    "SYSTEM_PATHS": re.compile(r"(?:/home/ramon|/root|/Users/ramon)[a-zA-Z0-9_\-\.\/]*"),
    "GENERIC_SECRET": re.compile(r'(?i)(password|passwd|secret|token|api_key|passphrase)\s*[:=]\s*["\']([^"\']+)["\']'),
    "OPENAI_KEY": re.compile(r"sk-[a-zA-Z0-9]{48}"),
    "ANTHROPIC_KEY": re.compile(r"sk-ant-api03-[a-zA-Z0-9\-_]{40,}"),
    "SSH_PRIVATE_KEY": re.compile(r"-----BEGIN [A-Z]+ PRIVATE KEY-----\s*[\s\S]*?-----END [A-Z]+ PRIVATE KEY-----"),
}


def sanitize_text(text: str) -> str:
    """Sanitiza datos sensibles usando mascaras opacas."""
    if not text:
        return ""
    text = PATTERNS["SSH_PRIVATE_KEY"].sub("[SSH_PRIVATE_KEY_REDACTADA]", text)
    text = PATTERNS["OPENAI_KEY"].sub("[OPENAI_API_KEY_REDACTADA]", text)
    text = PATTERNS["ANTHROPIC_KEY"].sub("[ANTHROPIC_API_KEY_REDACTADA]", text)
    text = PATTERNS["SYSTEM_PATHS"].sub("[RUTA_SISTEMA_REDACTADA]", text)
    text = PATTERNS["IP_ADDRESS"].sub("[IP_REDACTADA]", text)
    return PATTERNS["GENERIC_SECRET"].sub(r'\1: "[CREDENTIAL_REDACTADA]"', text)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        with open(file_path, encoding="utf-8") as f:  # noqa: PTH123
            content = f.read()
        with open(file_path, "w", encoding="utf-8") as f:  # noqa: PTH123
            f.write(sanitize_text(content))
    else:
        import sys

        sys.stdout.write(sanitize_text(sys.stdin.read()))
