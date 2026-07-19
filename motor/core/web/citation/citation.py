"""CitationEngine — citas y trazabilidad de fuentes (F24-B8).

Cada evidence tiene un evidence_id estable generado a partir de
(document_id, sentence_position, content_hash), lo que permite
referirse a piezas concretas de evidencia desde Knowledge Fusion,
memoria y agentes sin depender de índices de listas.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from motor.core.web.cleaner.url_utils import content_hash as _content_hash
from motor.core.web.cleaner.url_utils import get_document_id

if TYPE_CHECKING:
    from motor.core.web.models import WebDocument
    from motor.core.web.summarizer.summarizer import Summary


def make_evidence_id(
    document_id: str,
    sentence_position: int,
    doc_content_hash: str,
) -> str:
    """Genera un identificador estable para una pieza de evidencia."""
    raw = f"{document_id}:{sentence_position}:{doc_content_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Evidence:
    """Pieza de evidencia con trazabilidad completa a su origen.

    INMUTABLE: una vez creada, no cambia. Si la evidencia necesita
    actualizarse, se crea una nueva instancia. Esto garantiza que
    toda referencia a Evidence mantiene su valor original.

    Contiene toda la información necesaria para responder sin
    búsquedas adicionales: documento de origen, frase exacta,
    posición, hash, timestamp y calidad.
    """

    evidence_id: str
    document_url: str
    canonical_url: str | None
    title: str
    document_index: int
    sentence_position: int
    fragment: str
    content_hash: str
    document_id: str
    fetched_at: float
    quality_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "document_url": self.document_url,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "document_index": self.document_index,
            "sentence_position": self.sentence_position,
            "fragment": self.fragment,
            "content_hash": self.content_hash,
            "document_id": self.document_id,
            "fetched_at": self.fetched_at,
            "quality_score": self.quality_score,
        }


@dataclass
class CitationRecord:
    """Cita que vincula una frase del resumen con su evidencia."""

    evidence_id: str
    document_url: str
    title: str
    fragment: str
    citation_index: int
    document_index: int


@dataclass
class CitationBundle:
    """Agregado completo de resumen, citas, evidencias y trazabilidad.

    Permite demostrar de dónde proviene cada afirmación del resumen
    sin necesidad de búsquedas adicionales.
    """

    summary: str
    citations: list[CitationRecord]
    evidence: list[Evidence]
    traceability_report: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "citations": [
                dict(c.__dict__)
                for c in self.citations
            ],
            "evidence": [e.to_dict() for e in self.evidence],
            "traceability_report": self.traceability_report,
        }


class CitationEngine:
    """Genera citas y trazabilidad a partir de un resumen y sus documentos fuente.

    Cada frase del resumen se vincula a su evidencia original mediante
    evidence_id, permitiendo responder sin búsquedas adicionales:
    - ¿Qué documento la originó?
    - ¿Qué frase exacta la originó?
    - ¿Qué posición ocupaba en el original?
    - ¿Qué hash tenía el documento?
    - ¿Cuándo fue obtenido?
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build(
        self,
        summary: Summary,
        documents: list[WebDocument],
    ) -> CitationBundle:
        """Construye un CitationBundle a partir del resumen y documentos fuente.

        Args:
            summary: Resumen extractivo generado por ExtractiveSummarizer.
            documents: Documentos originales que se usaron para el resumen.
        """
        with self._lock:
            doc_map: dict[str, WebDocument] = {d.url: d for d in documents}
            evidence_map: dict[str, Evidence] = {}
            citations: list[CitationRecord] = []
            citations_per_doc: dict[str, int] = {}

            for sent_idx, origin in enumerate(summary.sentence_origins):
                url = origin["url"]
                doc = doc_map.get(url)
                if doc is None:
                    continue

                citations_per_doc[url] = citations_per_doc.get(url, 0) + 1
                doc_index = _find_doc_index(documents, url)

                canonical_url = (
                    doc.metadata.get("canonical_url")
                    if isinstance(doc.metadata, dict)
                    else None
                )
                doc_id = get_document_id(doc.url, canonical_url)
                doc_hash = _content_hash(doc.text or "")
                sent_pos = origin["position"]
                frag = summary.sentences[sent_idx]

                eid = make_evidence_id(doc_id, sent_pos, doc_hash)

                if eid not in evidence_map:
                    evidence_map[eid] = Evidence(
                        evidence_id=eid,
                        document_url=url,
                        canonical_url=canonical_url,
                        title=origin.get("title", ""),
                        document_index=doc_index,
                        sentence_position=sent_pos,
                        fragment=frag,
                        content_hash=doc_hash,
                        document_id=doc_id,
                        fetched_at=doc.extracted_at,
                        quality_score=doc.quality_score,
                    )

                citations.append(
                    CitationRecord(
                        evidence_id=eid,
                        document_url=url,
                        title=origin.get("title", ""),
                        fragment=frag,
                        citation_index=sent_idx,
                        document_index=doc_index,
                    )
                )

            report = {
                "total_citations": len(citations),
                "unique_documents": len(summary.source_documents),
                "evidence_count": len(evidence_map),
                "citations_per_document": citations_per_doc,
            }

            return CitationBundle(
                summary=summary.text,
                citations=citations,
                evidence=list(evidence_map.values()),
                traceability_report=report,
            )


def _find_doc_index(documents: list[WebDocument], url: str) -> int:
    for i, d in enumerate(documents):
        if d.url == url:
            return i
    return -1
