"""NormalizationStage: limpieza y normalización básica de Claims."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from motor.core.fusion.base import BaseStage
from motor.core.fusion.engine import FusionStage

if TYPE_CHECKING:
    from motor.core.fusion.models import FusionContext


_RE_WHITESPACE = re.compile(r"\s+")
_RE_PUNCTUATION = re.compile(r"[^\w\sáéíóúàèìòùäëïöüñçÁÉÍÓÚÀÈÌÒÙÄËÏÖÜÑÇ]")


class NormalizationStage(BaseStage):
    """Limpieza básica de texto en cada Claim.

    Aplica:
    - Eliminación de espacios múltiples
    - Eliminación de puntuación no esencial
    - Strip y lowercase

    No hace correferencia, desambiguación ni análisis semántico.
    """

    @property
    def stage(self) -> FusionStage:
        return FusionStage.NORMALIZATION

    @property
    def name(self) -> str:
        return "NormalizationStage"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _execute(self, context: FusionContext) -> FusionContext:
        for claim in context.claims:
            claim.normalized_text = self._normalize(claim.text)

        context.statistics["claims_normalized"] = len(context.claims)
        return context

    @classmethod
    def _normalize(cls, text: str) -> str:
        text = text.strip().lower()
        text = _RE_WHITESPACE.sub(" ", text)
        text = _RE_PUNCTUATION.sub("", text)
        return text.strip()
