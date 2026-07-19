"""MarkdownExtractor — extrae metadatos de documentos Markdown.

No requiere dependencias externas. Usa solo la biblioteca estándar y el parser
YAML incluido en Python.

Extrae:
  - título (desde frontmatter)
  - frontmatter completo (como dict)
  - tags
  - enlaces internos y externos
  - número de palabras
  - número de encabezados (por nivel)
  - tamaño en bytes
  - hash SHA-256
  - fecha de extracción
  - versión del extractor
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import UTC, datetime

import yaml

from knowledge.engine.extractors.base import ExtractionResult, get_registry
from knowledge.engine.ontology.internal import AssetRelationship, AssetSource, AssetType, KnowledgeAsset

_MD_MIMES = ["text/markdown", "text/x-markdown", "text/plain"]

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_INTERNAL_LINK_RE = re.compile(r"\[([^\]]+)\]\(([a-f0-9]{12}\.md)\)")
_EXTERNAL_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


class MarkdownExtractor:
    """Extractor para documentos Markdown.

    Uso:
        extractor = MarkdownExtractor()
        result = extractor.extract(source)
    """

    id: str = "markdown"
    version: str = "1.0.0"
    supported_mime_types: list[str] = _MD_MIMES
    cost: str = "O(1)"

    def extract(self, source: AssetSource) -> ExtractionResult:
        """Extrae metadatos de un archivo Markdown.

        Args:
            source: AssetSource con location apuntando al archivo .md.

        Returns:
            ExtractionResult con un KnowledgeAsset de tipo MARKDOWN.
        """
        t0 = time.monotonic()
        path_str = source.location

        try:
            import os as _os

            if not _os.path.exists(path_str):
                return ExtractionResult(
                    errors=[f"File not found: {path_str}"],
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

            content_bytes = _load_file(path_str)
            raw = content_bytes.decode("utf-8", errors="replace")
            content_sha256 = hashlib.sha256(content_bytes).hexdigest()
            size = len(content_bytes)

            # Extraer frontmatter YAML
            fm, body = _parse_frontmatter(raw)
            title = _extract_title(fm, body)
            tags = _extract_tags(fm)
            word_count = _count_words(body)
            headings = _count_headings(body)
            internal_links = _find_internal_links(body)
            external_links = _find_external_links(body)

            now = datetime.now(UTC).isoformat()

            asset = KnowledgeAsset(
                asset_id=content_sha256[:16],
                asset_type=AssetType.MARKDOWN,
                metadata={
                    "title": title,
                    "frontmatter": fm if fm else {},
                    "tags": tags,
                    "word_count": word_count,
                    "headings": headings,
                    "internal_links": internal_links,
                    "external_links": external_links,
                    "size": size,
                    "content_sha256": content_sha256,
                    "extracted_at": now,
                    "_extractor": self.id,
                    "_extractor_version": self.version,
                    "wraps": f"source:{path_str}",
                },
                source=source,
                quality=_compute_quality(tags, word_count, headings),
                created_at=now,
                updated_at=now,
                relationships=tuple(
                    AssetRelationship(target_id=link, relation="references") for link in internal_links
                ),
            )

            return ExtractionResult(
                asset=asset,
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        except Exception as exc:
            return ExtractionResult(
                errors=[f"Extraction error: {exc}"],
                duration_ms=(time.monotonic() - t0) * 1000,
            )


# ── Internal helpers ──────────────────────────────────────────────────────


def _load_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _parse_frontmatter(raw: str) -> tuple[dict | None, str]:
    """Parsea frontmatter YAML (--- ... ---). Retorna (frontmatter_dict, body)."""
    if not raw.startswith("---"):
        return None, raw
    end = raw.find("---", 3)
    if end == -1:
        return None, raw
    yaml_text = raw[3:end].strip()
    body = raw[end + 3 :].strip()
    try:
        fm = yaml.safe_load(yaml_text)
        if isinstance(fm, dict):
            return fm, body
    except yaml.YAMLError:
        pass  # noqa: S110
    return None, raw


def _extract_title(fm: dict | None, body: str) -> str:
    if fm and isinstance(fm, dict) and "title" in fm:
        return str(fm["title"])
    # Fallback: primer heading
    m = _HEADING_RE.search(body)
    if m:
        return m.group(2).strip()
    return ""


def _extract_tags(fm: dict | None) -> list[str]:
    if fm and isinstance(fm, dict):
        tags = fm.get("tags", [])
        if isinstance(tags, list):
            return [str(t) for t in tags]
        if isinstance(tags, str):
            return [t.strip() for t in tags.split(",") if t.strip()]
    return []


def _count_words(text: str) -> int:
    return len(text.split())


def _count_headings(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in _HEADING_RE.finditer(text):
        level = f"h{len(match.group(1))}"
        counts[level] = counts.get(level, 0) + 1
    return counts


def _find_internal_links(text: str) -> list[str]:
    return [m.group(2).replace(".md", "") for m in _INTERNAL_LINK_RE.finditer(text)]


def _find_external_links(text: str) -> list[str]:
    return [m.group(2) for m in _EXTERNAL_LINK_RE.finditer(text)]


def _compute_quality(tags: list[str], word_count: int, headings: dict[str, int]) -> float:
    """Calidad del documento: 0.0 - 1.0.

    Factores:
      - Tiene tags: +0.2
      - Tiene headings: +0.2
      - word_count > 50: +0.3
      - word_count > 200: +0.3 adicional
    """
    q = 0.3  # base
    if tags:
        q += 0.2
    if headings:
        q += 0.2
    if word_count > 50:
        q += 0.15
    if word_count > 200:
        q += 0.15
    return min(q, 1.0)


# ── Auto-registro ────────────────────────────────────────────────────────

_registry = get_registry()
_registry.register(MarkdownExtractor())
