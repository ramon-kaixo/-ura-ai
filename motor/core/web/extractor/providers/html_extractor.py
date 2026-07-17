"""HtmlExtractor — extracción de HTML sin dependencias externas (F24-B4).

Dos fases internas:
1. Limpieza del DOM (eliminar script, style, noscript, normalizar)
2. Conversión a WebDocument (título, texto, metadatos)
"""

from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from typing import Final

from motor.core.web.base import Extractor
from motor.core.web.models import WebDocument

_BLOCK_TAGS: Final = frozenset({
    "p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "ol", "ul", "blockquote", "pre", "tr", "td", "th",
    "section", "article", "nav", "header", "footer", "main",
    "figure", "figcaption", "details", "summary",
})

_SKIP_TAGS: Final = frozenset({
    "script", "style", "noscript", "svg", "iframe",
    "textarea", "select", "option",
})

_WHITESPACE_RE: Final = re.compile(r"[ \t]+")
_NEWLINE_RE: Final = re.compile(r"\n{3,}")


def detect_encoding(html: bytes, content_type: str | None = None) -> str:
    """Detecta la codificación de un documento HTML."""
    if html[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    head = html[:4096].decode("ascii", errors="replace").lower()
    m = re.search(r'<meta[^>]+charset="?([a-z0-9_-]+)"?', head)
    if m:
        return m.group(1)
    m = re.search(r'<\?xml[^>]+encoding="([^"]+)"', head)
    if m:
        return m.group(1)
    if content_type:
        m = re.search(r"charset=([a-z0-9_-]+)", content_type, re.IGNORECASE)
        if m:
            return m.group(1)
    return "utf-8"


def extract_metadata(html: str) -> dict[str, str]:
    """Extrae metadatos básicos del HTML sin parser completo."""
    meta: dict[str, str] = {}
    for m in re.finditer(
        r'<meta\s+([^>]+)>', html, re.IGNORECASE
    ):
        attrs = _parse_attrs(m.group(1))
        name = attrs.get("name", "").lower() if "name" in attrs else ""
        prop = attrs.get("property", "").lower() if "property" in attrs else ""
        content = attrs.get("content", "") if "content" in attrs else ""
        key = name or prop
        if key == "description":
            meta["description"] = content
        elif key == "author":
            meta["author"] = content
        elif key in ("og:locale", "language"):
            meta["language"] = content
        elif key == "article:published_time":
            meta["published_time"] = content
    match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if match:
        meta["title"] = match.group(1).strip()
    match = re.search(
        r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html, re.IGNORECASE
    )
    if match:
        meta["canonical_url"] = match.group(1)
    return meta


def _parse_attrs(attrs_str: str) -> dict[str, str]:
    """Parse attributes from a tag fragment."""
    result: dict[str, str] = {}
    for a in re.finditer(r'(\S+)\s*=\s*"([^"]*)"', attrs_str):
        result[a.group(1).lower()] = a.group(2)
    for a in re.finditer(r"(\S+)\s*=\s*'([^']*)'", attrs_str):
        if a.group(1).lower() not in result:
            result[a.group(1).lower()] = a.group(2)
    for a in re.finditer(r"(\S+)\s*=\s*(\S+)", attrs_str):
        k = a.group(1).lower()
        v = a.group(2)
        if k not in result and not v.startswith(("'", '"')):
            result[k] = v
    return result


class _HtmlCleaner(HTMLParser):
    """Fase 1: limpia HTML, extrae texto plano."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._result: list[str] = []
        self._skip_depth: int = 0
        self._title: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag_lower == "title" and not self._title:
            self._skip_depth += 1
        if self._skip_depth > 0:
            return
        if tag_lower in _BLOCK_TAGS and self._result and not self._result[-1].endswith("\n"):
            self._result.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in _SKIP_TAGS or (tag_lower == "title" and not self._title):
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        cleaned = _WHITESPACE_RE.sub(" ", data)
        if cleaned:
            self._result.append(cleaned)

    def get_text(self) -> str:
        return _NEWLINE_RE.sub("\n\n", "".join(self._result)).strip()


def _clean_html(html: str) -> str:
    """Fase 1: limpia el HTML y retorna texto plano."""
    if not html:
        return ""
    parser = _HtmlCleaner()
    parser.feed(html)
    return parser.get_text()


def _to_webdocument(text: str, url: str, meta: dict[str, str], html: str) -> WebDocument:
    """Fase 2: convierte texto limpio + metadatos a WebDocument."""
    wc = len(text.split()) if text else 0
    quality = min(1.0, wc / 500) if wc > 0 else 0.0
    return WebDocument(
        url=url,
        title=meta.get("title", ""),
        text=text,
        word_count=wc,
        quality_score=quality,
        source=meta.get("canonical_url", url),
        language=meta.get("language", ""),
        author=meta.get("author", ""),
        description=meta.get("description", ""),
        published_time=meta.get("published_time", ""),
    )


class HtmlExtractor(Extractor):
    """Extractor de HTML a WebDocument sin dependencias externas."""

    def __init__(self) -> None:
        self._name = "html"

    @property
    def name(self) -> str:
        return self._name

    def extract(self, html: str, url: str) -> WebDocument:
        t0 = time.monotonic()
        text = _clean_html(html)
        meta = extract_metadata(html)
        doc = _to_webdocument(text, url, meta, html)
        self._record_metrics(t0)
        return doc

    def extract_text(self, html: str) -> str:
        return _clean_html(html)

    def _record_metrics(self, t0: float) -> None:
        elapsed = time.monotonic() - t0
        self._last_extraction_time_ms = elapsed * 1000
