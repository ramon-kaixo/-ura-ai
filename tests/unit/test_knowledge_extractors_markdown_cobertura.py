"""Tests de cobertura para knowledge/engine/extractors/markdown.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.engine.extractors.markdown import (
    MarkdownExtractor,
    _compute_quality,
    _count_headings,
    _count_words,
    _extract_tags,
    _extract_title,
    _find_external_links,
    _find_internal_links,
    _load_file,
    _parse_frontmatter,
)
from knowledge.engine.ontology.internal import AssetSource, AssetType

MD_SIMPLE = "# Título\n\nTexto corto."
MD_FULL = """---
title: Mi Documento
tags: [python, ura]
---
# Título H1

## Subtítulo

Párrafo con [enlace interno](0123456789ab.md) y [web](https://example.com/x).

Palabras adicionales para superar los umbrales de calidad del extractor markdown de conocimiento.
"""


def _source(tmp_path: Path, content: str = MD_FULL) -> AssetSource:
    p = tmp_path / "doc.md"
    p.write_text(content)
    return AssetSource(kind="filesystem", location=str(p), fetched_at="")


def test_extract_ok(tmp_path) -> None:
    src = _source(tmp_path)
    result = MarkdownExtractor().extract(src)
    assert result.errors == []
    asset = result.asset
    assert asset is not None
    assert asset.asset_type == AssetType.MARKDOWN
    meta = asset.metadata
    assert meta["title"] == "Mi Documento"
    assert meta["tags"] == ["python", "ura"]
    assert meta["word_count"] > 0
    assert meta["headings"] == {"h1": 1, "h2": 1}
    assert meta["internal_links"] == ["0123456789ab"]
    assert meta["external_links"] == ["https://example.com/x"]
    assert meta["content_sha256"]
    assert meta["size"] == len(MD_FULL.encode())
    assert meta["_extractor"] == "markdown"
    assert asset.relationships and asset.relationships[0].relation == "references"
    assert result.duration_ms >= 0


def test_extract_archivo_no_existe(tmp_path) -> None:
    src = AssetSource(kind="filesystem", location=str(tmp_path / "no.md"), fetched_at="")
    result = MarkdownExtractor().extract(src)
    assert result.errors and "File not found" in result.errors[0]
    assert result.asset is None


def test_extract_permiso_denegado(tmp_path) -> None:
    p = tmp_path / "d.md"
    p.write_text("x")
    p.chmod(0o000)
    try:
        src = AssetSource(kind="filesystem", location=str(p), fetched_at="")
        result = MarkdownExtractor().extract(src)
        assert result.errors and "Extraction error" in result.errors[0]
    finally:
        p.chmod(0o644)


def test_parse_frontmatter_completo() -> None:
    fm, body = _parse_frontmatter(MD_FULL)
    assert fm == {"title": "Mi Documento", "tags": ["python", "ura"]}
    assert body.startswith("# Título H1")


def test_parse_frontmatter_sin() -> None:
    fm, body = _parse_frontmatter("hola")
    assert fm is None
    assert body == "hola"


def test_parse_frontmatter_incompleto() -> None:
    fm, body = _parse_frontmatter("---\ntitle: x")
    assert fm is None
    assert body == "---\ntitle: x"


def test_parse_frontmatter_yaml_invalido() -> None:
    fm, body = _parse_frontmatter("---\n:: not yaml ::\n---\nresto")
    assert fm is None
    assert body == "---\n:: not yaml ::\n---\nresto"


def test_parse_frontmatter_no_dict() -> None:
    fm, body = _parse_frontmatter("---\n- a\n- b\n---\ncuerpo")
    assert fm is None
    assert body == "---\n- a\n- b\n---\ncuerpo"


def test_extract_title_desde_fm() -> None:
    assert _extract_title({"title": "T"}, "x") == "T"


def test_extract_title_fallback_heading() -> None:
    assert _extract_title(None, "# Hola\nx") == "Hola"


def test_extract_title_vacio() -> None:
    assert _extract_title({}, "sin headings") == ""


def test_extract_tags_lista() -> None:
    assert _extract_tags({"tags": [1, "dos"]}) == ["1", "dos"]


def test_extract_tags_string() -> None:
    assert _extract_tags({"tags": "a, b ,c"}) == ["a", "b", "c"]


def test_extract_tags_vacio() -> None:
    assert _extract_tags(None) == []
    assert _extract_tags({"tags": 42}) == []


def test_count_words() -> None:
    assert _count_words("hola mundo") == 2
    assert _count_words("") == 0


def test_count_headings() -> None:
    assert _count_headings("# a\n## b\n# c") == {"h1": 2, "h2": 1}
    assert _count_headings("sin") == {}


def test_find_internal_links() -> None:
    assert _find_internal_links("[x](0123456789ab.md) y [z](000000000000.md)") == ["0123456789ab", "000000000000"]


def test_find_external_links() -> None:
    assert _find_external_links("[x](https://a.com) [y](http://b.org)") == ["https://a.com", "http://b.org"]


def test_compute_quality() -> None:
    assert _compute_quality([], 0, {}) == 0.3
    assert _compute_quality(["t"], 10, {"h1": 1}) == pytest.approx(0.7)
    assert _compute_quality(["t"], 100, {"h1": 1}) == pytest.approx(0.85)
    assert _compute_quality(["t"], 300, {"h1": 1}) == pytest.approx(1.0)


def test_load_file(tmp_path) -> None:
    p = tmp_path / "b.md"
    p.write_bytes(b"\x00\x01")
    assert _load_file(str(p)) == b"\x00\x01"


def test_registry() -> None:
    from knowledge.engine.extractors.base import get_registry

    ext = get_registry().get("markdown")
    assert ext is not None
    assert ext.supported_mime_types == ["text/markdown", "text/x-markdown", "text/plain"]
