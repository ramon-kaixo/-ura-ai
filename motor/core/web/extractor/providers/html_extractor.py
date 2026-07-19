"""HtmlExtractor — extracción de HTML sin dependencias externas (F24-B4).

Dos fases internas:
1. Limpieza del DOM (eliminar script, style, noscript, normalizar)
2. Conversión a WebDocument (título, texto, metadatos)
"""

from __future__ import annotations

import re
import time
from html.parser import HTMLParser

from motor.core.web.base import Extractor
from motor.core.web.models import WebDocument

_BLOCK_TAGS: frozenset = frozenset({
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "blockquote", "section", "article", "pre",
    "br", "tr", "th", "td",
})
_SKIP_TAGS: frozenset = frozenset({
    "script", "style", "noscript", "iframe", "svg",
    "canvas", "form", "input", "select", "textarea",
    "button", "nav", "footer", "header", "aside",
})
_WHITESPACE_RE: re.Pattern = re.compile(r"[ \t]+")
_NEWLINE_RE: re.Pattern = re.compile(r"\n{3,}")


def detect_encoding(html: bytes, content_type: str | None = None) -> str:
    """Detecta codificación desde BOM, meta charset, XML encoding o content-type."""
    if html[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    text = html[:2048].decode("ascii", errors="replace")
    m = re.search(r'<meta[^>]+charset=["\']?([a-zA-Z0-9_-]+)', text, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    m = re.search(r'<\?xml[^>]+encoding=["\']([^"\']+)', text, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    if content_type:
        m = re.search(r"charset=([a-zA-Z0-9_-]+)", content_type, re.IGNORECASE)
        if m:
            return m.group(1).lower()
    return "utf-8"


def extract_metadata(
    html: str,
) -> dict[str, str | None]:
    """Extrae metadatos básicos desde <meta> y <link> tags."""
    meta = {}
    for m in re.finditer(
        r'<meta\s+[^>]*?(?:name|property)\s*=\s*["\']([^"\']+)["\'][^>]*?'
        r'content\s*=\s*["\']([^"\']*)["\']',
        html,
        re.IGNORECASE,
    ):
        key = m.group(1).strip().lower().replace(":", "_")
        val = m.group(2).strip()
        meta[key] = val
    # También capturar content antes de name
    for m in re.finditer(
        r'<meta\s+[^>]*?content\s*=\s*["\']([^"\']*)["\'][^>]*?'
        r'(?:name|property)\s*=\s*["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    ):
        key = m.group(2).strip().lower().replace(":", "_")
        val = m.group(1).strip()
        if key not in meta:
            meta[key] = val
    # published_time from article:published_time
    for key in list(meta):
        if "article:published_time" in key or "published_time" in key:
            meta["published_time"] = meta[key]
            break
    # canonical
    m = re.search(
        r'<link\s+[^>]*?rel\s*=\s*["\']canonical["\'][^>]*?href\s*=\s*["\']'
        r'([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if m:
        meta["canonical_url"] = m.group(1)
    return meta


def _parse_attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {k: v for k, v in attrs if v is not None}


class _HtmlCleaner(HTMLParser):
    """Limpieza del DOM: extrae texto eliminando skip tags y normalizando."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._result: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        if tag_lower in _BLOCK_TAGS and self._result and not self._result[-1].endswith("\n"):
            self._result.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in _SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = _WHITESPACE_RE.sub(" ", data)
        if text:
            self._result.append(text)

    def get_text(self) -> str:
        raw = "".join(self._result)
        return _NEWLINE_RE.sub("\n\n", raw).strip()


def _clean_html(html: str) -> str:
    """Fase 1: limpia el HTML y devuelve texto plano normalizado."""
    cleaner = _HtmlCleaner()
    cleaner.feed(html)
    return cleaner.get_text()


def _to_webdocument(
    html: str,
    url: str,
    text: str,
    start_time: float,
) -> WebDocument:
    """Fase 2: construye un WebDocument desde HTML y texto extraído."""
    meta = extract_metadata(html)
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else None
    word_count = len(text.split()) if text else 0
    quality_score = min(1.0, word_count / 500) if word_count > 0 else 0.0
    return WebDocument(
        url=url,
        title=title or "",
        text=text,
        html=html,
        word_count=word_count,
        quality_score=quality_score,
        metadata={
            "extractor": "html",
            "extraction_time_ms": (time.monotonic() - start_time) * 1000,
            "author": meta.get("author"),
            "description": meta.get("description"),
            "language": meta.get("language"),
            "published_time": meta.get("published_time"),
            "canonical_url": meta.get("canonical_url"),
        },
    )


class HtmlExtractor(Extractor):
    """Extractor de HTML público sin dependencias externas."""

    @property
    def name(self) -> str:
        return "html"

    def extract_text(self, html: str) -> str:
        return _clean_html(html)

    def extract(self, html: str, url: str) -> WebDocument:
        t0 = time.monotonic()
        text = _clean_html(html)
        return _to_webdocument(html, url, text, t0)
