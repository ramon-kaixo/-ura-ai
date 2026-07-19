"""Utilidades de normalización de URLs.

Separa dos identificadores:
- document_id: estable, derivado de la URL canónica (o URL original).
- content_hash: SHA-256 del texto normalizado, para detectar duplicados.
"""

from __future__ import annotations

import hashlib
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Normaliza una URL: esquema/host a lowercase, elimina fragmento, slash final.

    Ejemplos:
        HTTPS://Example.COM/Path/ -> https://example.com/Path
        http://example.com/page#fragment -> http://example.com/page
        http://example.com/ -> http://example.com/
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path
    if path == "/":
        path = "/"
    elif path.endswith("/"):
        path = path.rstrip("/") or "/"
    elif not path:
        path = "/"
    # eliminar fragmento
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def get_document_id(
    url: str,
    canonical_url: str | None = None,
) -> str:
    """Genera un identificador estable para un documento.

    Usa canonical_url si existe, sino normaliza la URL original.
    """
    raw = canonical_url or url
    return normalize_url(raw)


def content_hash(text: str) -> str:
    """SHA-256 del texto normalizado (sin espacios extra)."""
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
