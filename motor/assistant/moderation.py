"""ContentModeration — filtra contenido dañino en entradas y salidas."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_HARMFUL_PATTERNS = re.compile(
    r"(?i)\b(instrucciones\s+para\s+(cometer|hacer|fabricar|crear)\s+"
    r"|c[oó]mo\s+(matar|robar|asaltar|hackear|violar|suicidar)"
    r"|arma\s+(qu[ií]mica|biol[oó]gica|casera|de\s+fuego)"
    r"|explosivos?\s+caseros?"
    r"|nuclear\s+(bomba|arma|dispositivo)"
    r"|pornograf[ií]a\s+infantil"
    r"|violaci[oó]n|abus[oó]\s+sexual|incesto"
    r"|tr[aá]fico\s+de\s+(personas|[dD]rogas|armas)"
    r"|suicidio\s+(asistido|m[eé]todo|forma)"
    r"|nunca\s+deber[ií]as|no\s+le\s+d[ií]gas\s+a\s+nadie"
    r"|instrucciones\s+secretas|ignora\s+las\s+instrucciones)"
    r"\b",
)


@dataclass
class ModerationResult:
    flagged: bool
    categories: list[str] = field(default_factory=list)
    score: float = 0.0
    sanitized_text: str = ""


class ContentModerator:
    def moderate_input(self, text: str) -> ModerationResult:
        if not text:
            return ModerationResult(flagged=False)

        match = _HARMFUL_PATTERNS.search(text)
        if match:
            return ModerationResult(
                flagged=True,
                categories=["harmful_content"],
                score=1.0,
                sanitized_text=_HARMFUL_PATTERNS.sub("[contenido bloqueado]", text),
            )
        return ModerationResult(flagged=False)

    def moderate_output(self, text: str) -> ModerationResult:
        if not text:
            return ModerationResult(flagged=False)

        match = _HARMFUL_PATTERNS.search(text)
        if match:
            return ModerationResult(
                flagged=True,
                categories=["harmful_output"],
                score=0.9,
                sanitized_text=_HARMFUL_PATTERNS.sub("[contenido bloqueado]", text),
            )
        return ModerationResult(flagged=False)

    def is_safe(self, text: str) -> bool:
        return not _HARMFUL_PATTERNS.search(text)
