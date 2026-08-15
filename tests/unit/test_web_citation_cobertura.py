"""Cobertura 100x100 de motor/core/web/citation/citation.py (TASK-20260815-003).

Cubre make_evidence_id (estabilidad del id), Evidence/CitationRecord/
CitationBundle (to_dict), y CitationEngine.build con todas las ramas:
documento no encontrado, metadata dict/no-dict, evidencia duplicada
(reutilizada sin crear entrada nueva), citas repetidas por documento y
_find_doc_index sin coincidencia (llamada directa a la función privada).

Sin dependencias externas: solo motor.core.web + stdlib.
"""

from __future__ import annotations

import pytest

from motor.core.web.citation.citation import (
    CitationBundle,
    CitationEngine,
    CitationRecord,
    Evidence,
    _find_doc_index,
    make_evidence_id,
)
from motor.core.web.models import WebDocument
from motor.core.web.summarizer.summarizer import Summary


def _make_doc(
    url: str,
    title: str = "Ejemplo",
    text: str = "Frase de ejemplo con contenido suficiente.",
    *,
    metadata: dict[str, str] | None = None,
    quality: float = 1.0,
) -> WebDocument:
    return WebDocument(
        url=url,
        title=title,
        text=text,
        html="<p>html</p>",
        metadata=metadata,
        quality_score=quality,
    )


class TestMakeEvidenceId:
    """Identificador estable de evidencia."""

    def test_estable_y_corto(self) -> None:
        eid = make_evidence_id("doc1", 3, "hash1")
        assert len(eid) == 16
        assert isinstance(eid, str)
        assert make_evidence_id("doc1", 3, "hash1") == eid

    def test_cambia_con_sentencia(self) -> None:
        base = make_evidence_id("doc1", 3, "hash1")
        assert make_evidence_id("doc1", 4, "hash1") != base

    def test_cambia_con_hash(self) -> None:
        base = make_evidence_id("doc1", 3, "hash1")
        assert make_evidence_id("doc1", 3, "hash2") != base


class TestEvidence:
    """Dataclass Evidence."""

    def test_frozen(self) -> None:
        e = Evidence(
            evidence_id="e1",
            document_url="https://example.com/1",
            canonical_url=None,
            title="T",
            document_index=0,
            sentence_position=1,
            fragment="F",
            content_hash="h",
            document_id="d",
            fetched_at=1.5,
            quality_score=0.9,
        )
        with pytest.raises(AttributeError):
            e.evidence_id = "other"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        e = Evidence(
            evidence_id="e1",
            document_url="https://example.com/1",
            canonical_url="https://example.com/canon",
            title="T",
            document_index=2,
            sentence_position=3,
            fragment="F",
            content_hash="h",
            document_id="d",
            fetched_at=1.5,
            quality_score=0.9,
        )
        d = e.to_dict()
        assert d["evidence_id"] == "e1"
        assert d["canonical_url"] == "https://example.com/canon"
        assert d["document_index"] == 2
        assert d["fetched_at"] == 1.5


class TestCitationRecordAndBundle:
    """Citación y agregado."""

    def test_citation_record_fields(self) -> None:
        cr = CitationRecord(
            evidence_id="e1",
            document_url="https://example.com/1",
            title="T",
            fragment="F",
            citation_index=0,
            document_index=1,
        )
        assert cr.evidence_id == "e1"
        assert cr.citation_index == 0
        assert cr.document_index == 1

    def test_bundle_to_dict(self) -> None:
        cr = CitationRecord(
            evidence_id="e1",
            document_url="https://example.com/1",
            title="T",
            fragment="F",
            citation_index=0,
            document_index=0,
        )
        e = Evidence(
            evidence_id="e1",
            document_url="https://example.com/1",
            canonical_url=None,
            title="T",
            document_index=0,
            sentence_position=0,
            fragment="F",
            content_hash="h",
            document_id="d",
            fetched_at=1.0,
            quality_score=1.0,
        )
        b = CitationBundle(summary="S", citations=[cr], evidence=[e], traceability_report={"k": 1})
        d = b.to_dict()
        assert d["summary"] == "S"
        assert d["citations"] == [dict(cr.__dict__)]
        assert d["evidence"][0]["evidence_id"] == "e1"
        assert d["traceability_report"] == {"k": 1}

    def test_bundle_to_dict_defaults(self) -> None:
        b = CitationBundle(summary="", citations=[], evidence=[])
        d = b.to_dict()
        assert d["citations"] == []
        assert d["evidence"] == []
        assert d["traceability_report"] == {}


class TestCitationEngine:
    """Motor de citas completo."""

    def test_build_con_origenes_validos(self) -> None:
        doc = _make_doc("https://example.com/a", metadata={"canonical_url": "https://example.com/canon"})
        summary = Summary(
            text="Frase uno. Frase dos.",
            sentences=["Frase uno.", "Frase dos."],
            source_documents=["https://example.com/a"],
            sentence_origins=[
                {"url": "https://example.com/a", "title": "T", "position": 0},
                {"url": "https://example.com/a", "title": "T", "position": 1},
            ],
            compression_ratio=0.5,
        )
        bundle = CitationEngine().build(summary, [doc])
        assert len(bundle.citations) == 2
        assert len(bundle.evidence) == 2
        assert bundle.summary == "Frase uno. Frase dos."
        assert bundle.traceability_report["total_citations"] == 2
        assert bundle.traceability_report["unique_documents"] == 1
        assert bundle.traceability_report["citations_per_document"] == {"https://example.com/a": 2}
        e = bundle.evidence[0]
        assert e.canonical_url == "https://example.com/canon"
        assert e.document_id == "https://example.com/canon"
        assert e.document_index == 0
        assert e.fragment == "Frase uno."
        assert e.quality_score == 1.0

    def test_build_evidencia_duplicada_se_reutiliza(self) -> None:
        # Dos frases en la MISMA posición y mismo doc → mismo evidence_id
        summary = Summary(
            text="A A",
            sentences=["A", "A"],
            source_documents=["https://example.com/a"],
            sentence_origins=[
                {"url": "https://example.com/a", "position": 0},
                {"url": "https://example.com/a", "position": 0},
            ],
            compression_ratio=0.0,
        )
        bundle = CitationEngine().build(summary, [doc := _make_doc("https://example.com/a")])
        assert len(bundle.citations) == 2
        assert len(bundle.evidence) == 1  # evidencia reutilizada
        assert bundle.evidence[0].document_url == doc.url

    def test_build_documento_sin_metadata(self) -> None:
        doc = _make_doc("https://example.com/a")  # metadata=None
        summary = Summary(
            text="Solo",
            sentences=["Solo."],
            source_documents=["https://example.com/a"],
            sentence_origins=[{"url": "https://example.com/a", "position": 0}],
            compression_ratio=0.0,
        )
        bundle = CitationEngine().build(summary, [doc])
        assert bundle.evidence[0].canonical_url is None
        assert bundle.evidence[0].document_id == "https://example.com/a"

    def test_build_origen_sin_documento_se_ignora(self) -> None:
        summary = Summary(
            text="Fantasma",
            sentences=["Fantasma."],
            source_documents=[],
            sentence_origins=[{"url": "https://example.com/no-existe", "position": 0}],
            compression_ratio=0.0,
        )
        bundle = CitationEngine().build(summary, [])
        assert bundle.citations == []
        assert bundle.evidence == []
        assert bundle.traceability_report["total_citations"] == 0

    def test_build_metadatos_dict_sin_canonical(self) -> None:
        doc = _make_doc("https://example.com/a", metadata={"author": "x"})
        summary = Summary(
            text="Solo",
            sentences=["Solo."],
            source_documents=["https://example.com/a"],
            sentence_origins=[{"url": "https://example.com/a", "position": 0}],
            compression_ratio=0.0,
        )
        bundle = CitationEngine().build(summary, [doc])
        assert bundle.evidence[0].canonical_url is None
        assert bundle.evidence[0].document_id == "https://example.com/a"

    def test_build_title_desde_origin(self) -> None:
        doc = _make_doc("https://example.com/a")
        summary = Summary(
            text="X",
            sentences=["X."],
            source_documents=["https://example.com/a"],
            sentence_origins=[{"url": "https://example.com/a", "title": "Titulo Original", "position": 0}],
            compression_ratio=0.0,
        )
        bundle = CitationEngine().build(summary, [doc])
        assert bundle.evidence[0].title == "Titulo Original"
        assert bundle.citations[0].title == "Titulo Original"


class TestFindDocIndex:
    """Búsqueda de índice de documento (incluye rama no encontrado)."""

    def test_encuentra_indice(self) -> None:
        docs = [_make_doc("https://example.com/a"), _make_doc("https://example.com/b")]
        assert _find_doc_index(docs, "https://example.com/b") == 1

    def test_no_encontrado_devuelve_menos_uno(self) -> None:
        docs = [_make_doc("https://example.com/a")]
        assert _find_doc_index(docs, "https://example.com/nope") == -1

    def test_lista_vacia(self) -> None:
        assert _find_doc_index([], "https://example.com/a") == -1
