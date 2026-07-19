"""PdfExtractor — extrae metadatos de documentos PDF.

Dependencias obligatorias:
  - PyMuPDF (fitz)

Dependencias opcionales:
  - pytesseract (OCR para páginas sin texto)

Extrae:
  - páginas, título, autor, subject, keywords, creación
  - texto completo (por página, streaming)
  - metadatos técnicos (PDF version, encryption status)
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge.engine.extractors.base import (
    ExtractionResult,
    _check_import,
    _hash_stream,
    get_registry,
)
from knowledge.engine.ontology.internal import AssetSource, AssetType, KnowledgeAsset

log = logging.getLogger("ura.knowledge.extractors.pdf")

_PDF_MIMES = ["application/pdf"]

MAX_PAGES = 10_000
MAX_PDF_SIZE = 500 * 1024 * 1024

_HAS_FITZ = _check_import("fitz", "PyMuPDF")
_HAS_TESSERACT = _check_import("pytesseract", "pytesseract")


class PdfExtractor:
    """Extractor para documentos PDF.

    Uso:
        extractor = PdfExtractor()
        result = extractor.extract(source)
    """

    id: str = "pdf"
    version: str = "1.0.0"
    supported_mime_types: list[str] = _PDF_MIMES
    cost: str = "O(n)"

    def extract(self, source: AssetSource) -> ExtractionResult:
        t0 = time.monotonic()
        path_str = source.location

        if not Path(path_str).exists():
            return ExtractionResult(
                errors=[f"File not found: {path_str}"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        try:
            content_sha256, size = _hash_stream(path_str)

            if size > MAX_PDF_SIZE:
                return ExtractionResult(
                    errors=[f"File too large: {size} bytes (max {MAX_PDF_SIZE})"],
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

            now = datetime.now(UTC).isoformat()
            metadata: dict[str, Any] = {
                "size": size,
                "content_sha256": content_sha256,
                "_extractor": self.id,
                "_extractor_version": self.version,
                "wraps": f"source:{path_str}",
                "extracted_at": now,
            }

            if _HAS_FITZ:
                self._extract_with_fitz(path_str, metadata)
            else:
                log.warning("PyMuPDF not available, extracting basic metadata for %s", path_str)
                metadata["_degraded"] = True
                metadata["_degraded_reason"] = "PyMuPDF not installed"

            asset = KnowledgeAsset(
                asset_id=content_sha256[:16],
                asset_type=AssetType.PDF,
                metadata=metadata,
                source=source,
                quality=_compute_pdf_quality(metadata),
                created_at=now,
                updated_at=now,
            )

            return ExtractionResult(
                asset=asset,
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        except PdfLimitError as exc:
            return ExtractionResult(
                errors=[str(exc)],
                duration_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            log.exception("PDF extraction error for %s", path_str)
            return ExtractionResult(
                errors=[f"Extraction error: {exc}"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

    def _extract_with_fitz(self, path_str: str, metadata: dict[str, Any]) -> None:
        import fitz

        doc = fitz.open(path_str)
        try:
            num_pages = doc.page_count
            if num_pages > MAX_PAGES:
                msg = f"PDF has {num_pages} pages (max {MAX_PAGES})"
                raise PdfLimitError(msg)

            metadata["pages"] = num_pages
            metadata["pdf_version"] = doc.pdf_version if hasattr(doc, "pdf_version") else ""
            metadata["is_encrypted"] = doc.is_encrypted
            metadata["is_pdf"] = doc.is_pdf

            self._extract_metadata_fields(doc, metadata)

            full_text = self._extract_text(doc, num_pages)
            metadata["text_length"] = sum(len(t) for t in full_text)
            metadata["text_preview"] = full_text[0][:500] if full_text else ""

            self._check_text_or_ocr(doc, num_pages, full_text, metadata)

            log.info(
                "Extracted PDF: %s (%d pages, %d bytes, text=%s)",
                path_str,
                num_pages,
                metadata.get("size", 0),
                metadata.get("has_text"),
            )

        finally:
            doc.close()

    @staticmethod
    def _extract_metadata_fields(doc: Any, metadata: dict[str, Any]) -> None:
        fm = doc.metadata
        if not fm:
            return
        for key, field_name in (
            ("title", "title"),
            ("author", "author"),
            ("subject", "subject"),
            ("keywords", "keywords"),
            ("creator", "creator"),
            ("producer", "producer"),
            ("creationDate", "creation_date"),
            ("modDate", "modification_date"),
        ):
            val = fm.get(key, "")
            if val:
                metadata[field_name] = val

    @staticmethod
    def _extract_text(doc: Any, num_pages: int) -> list[str]:
        full_text: list[str] = []
        for i in range(num_pages):
            page = doc[i]
            full_text.append(page.get_text())
        return full_text

    def _check_text_or_ocr(
        self,
        doc: Any,
        num_pages: int,
        full_text: list[str],
        metadata: dict[str, Any],
    ) -> None:
        if not full_text or all(not t.strip() for t in full_text):
            metadata["has_text"] = False
            if _HAS_TESSERACT:
                self._run_ocr(doc, num_pages, metadata)
            else:
                metadata["ocr_performed"] = False
        else:
            metadata["has_text"] = True
            metadata["ocr_performed"] = False

    @staticmethod
    def _run_ocr(doc: Any, num_pages: int, metadata: dict[str, Any]) -> None:
        import pytesseract

        ocr_texts: list[str] = []
        for i in range(num_pages):
            page = doc[i]
            pix = page.get_pixmap()
            img_bytes = pix.tobytes("png")
            ocr_texts.append(pytesseract.image_to_string(img_bytes))
        metadata["ocr_text_length"] = sum(len(t) for t in ocr_texts)
        metadata["ocr_performed"] = True


class PdfLimitError(ValueError):
    """El PDF excede los límites establecidos."""


def _compute_pdf_quality(metadata: dict[str, Any]) -> float:
    q = 0.3
    if metadata.get("pages", 0) > 0:
        q += 0.15
    if metadata.get("title"):
        q += 0.15
    if metadata.get("author"):
        q += 0.1
    if metadata.get("text_length", 0) > 100:
        q += 0.15
    if metadata.get("keywords"):
        q += 0.15
    if metadata.get("has_text", False) or metadata.get("ocr_performed", False):
        q += 0.1
    return min(q, 1.0)


_registry = get_registry()
_registry.register(PdfExtractor())
