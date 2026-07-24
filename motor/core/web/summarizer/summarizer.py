"""ExtractiveSummarizer — resumen extractivo sin LLM (F24-B7).

Cada frase del resumen es copia exacta del original para facilitar
trazabilidad en fases posteriores (B8 citas).
"""

from __future__ import annotations

import math
import re
import threading
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.core.web.models import WebDocument

# Mínimo de caracteres para considerar una frase válida
_MIN_SENTENCE_LEN = 2
# Por debajo de esta longitud la frase se considera muy corta
_IDEAL_MIN = 10
# Por encima de esta longitud la frase se considera muy larga
_IDEAL_MAX = 40
# Saturación de repeticiones de un término en TF
_MAX_TF = 0.3


@dataclass
class SentenceInfo:
    """Información de una frase extraída con su origen."""

    text: str
    score: float
    position: int
    document_url: str
    document_title: str


@dataclass
class Summary:
    """Resumen extractivo con trazabilidad completa."""

    text: str
    sentences: list[str]
    source_documents: list[str]
    sentence_origins: list[dict[str, Any]]
    compression_ratio: float


def split_sentences(text: str) -> list[str]:
    """Divide texto en frases. No modifica el contenido de las frases."""
    # Normalizar saltos de línea primero
    text = re.sub(r"\n+", " ", text)
    # Dividir por puntuación final seguida de espacio+mayúscula o fin
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z¿¡\"\'\(\[])|(?<=[.!?])$", text.strip())
    result = []
    for part in parts:
        p = part.strip()
        if len(p) >= _MIN_SENTENCE_LEN:
            result.append(p)
        elif result and p:
            # Frase demasiado corta: la anexamos a la anterior
            result[-1] = result[-1] + " " + part
    return result or [text.strip()]


def _tf_scores(text: str) -> dict[str, float]:
    """Calcula TF para cada término en el texto."""
    words = re.findall(r"\w+", text.lower())
    total = len(words)
    if total == 0:
        return {}
    counts = Counter(words)
    return {w: min(c / total, _MAX_TF) for w, c in counts.items()}


def _title_overlap(title: str, sentence: str) -> float:
    """Fracción de palabras del título presentes en la frase."""
    title_words = set(re.findall(r"\w+", title.lower()))
    sent_words = set(re.findall(r"\w+", sentence.lower()))
    if not title_words:
        return 0.0
    return len(title_words & sent_words) / len(title_words)


def _length_score(n_words: int) -> float:
    """Puntuación de longitud: Gaussiana centrada en 20 palabras."""
    return math.exp(-(((n_words - 20) / 15) ** 2))


def _position_score(idx: int, total: int) -> float:
    """Puntuación de posición: favorece frases tempranas."""
    if total <= 1:
        return 1.0
    return 1.0 - (idx / (total - 1)) * 0.5


def score_sentence(
    sentence: str,
    tf: dict[str, float],
    title: str,
    position: int,
    total_sentences: int,
) -> float:
    """Calcula puntuación combinada para una frase."""
    words = re.findall(r"\w+", sentence.lower())
    if not words:
        return 0.0

    n_words = len(words)
    avg_tf = sum(tf.get(w, 0) for w in words) / n_words
    title_score = _title_overlap(title, sentence)
    length = _length_score(n_words)
    pos = _position_score(position, total_sentences)

    return avg_tf * 0.4 + title_score * 0.3 + length * 0.2 + pos * 0.1


class ExtractiveSummarizer:
    """Resumidor extractivo basado en puntuación de frases.

    - Sin dependencias externas
    - Sin LLM
    - Frases literales del original (sin modificación)
    - Soporta uno o varios documentos
    - Trazabilidad: cada frase registra su documento de origen
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def summarize(
        self,
        documents: list[WebDocument],
        max_length: int = 10,
    ) -> Summary:
        """Genera resumen extractivo a partir de uno o varios documentos.

        Args:
            documents: Documentos a resumir.
            max_length: Número máximo de frases en el resumen.

        """
        with self._lock:
            candidates: list[SentenceInfo] = []
            seen: set[str] = set()
            seen_urls: set[str] = set()

            for doc in documents:
                url = doc.url
                title = doc.title or ""
                text = doc.text or ""
                seen_urls.add(url)

                tfs = _tf_scores(text)
                sentences = split_sentences(text)

                for i, sent in enumerate(sentences):
                    sent_stripped = sent.strip()
                    if not sent_stripped:
                        continue
                    sent_lower = sent_stripped.lower()
                    if sent_lower in seen:
                        continue
                    seen.add(sent_lower)
                    score = score_sentence(sent, tfs, title, i, len(sentences))
                    candidates.append(
                        SentenceInfo(
                            text=sent_stripped,
                            score=round(score, 4),
                            position=i,
                            document_url=url,
                            document_title=title,
                        ),
                    )

            # Seleccionar mejores frases
            candidates.sort(key=lambda c: (-c.score, c.position))
            selected = candidates[:max_length]

            # Reordenar por posición original + documento
            selected.sort(key=lambda c: (list(seen_urls).index(c.document_url), c.position))

            final_sentences = [s.text for s in selected]
            total_words_original = sum(len(re.findall(r"\w+", doc.text or "")) for doc in documents)
            summary_words = sum(len(re.findall(r"\w+", s)) for s in final_sentences)
            compression = (
                round(1.0 - (summary_words / max(1, total_words_original)), 4) if total_words_original > 0 else 0.0
            )

            return Summary(
                text=" ".join(final_sentences),
                sentences=final_sentences,
                source_documents=list(seen_urls),
                sentence_origins=[
                    {
                        "url": s.document_url,
                        "title": s.document_title,
                        "position": s.position,
                        "score": s.score,
                    }
                    for s in selected
                ],
                compression_ratio=compression,
            )
