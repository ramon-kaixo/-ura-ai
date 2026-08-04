"""Tests para knowledge/engine/parser.py — parseo de Markdown → KnowledgeObject.

Funciones puras sobre SourceObject: frontmatter, body, relaciones y errores KE0xx.
"""
from __future__ import annotations

from knowledge.engine.models import CompileError, KnowledgeObject, SourceObject, doc_id_from_path
from knowledge.engine.parser import parse_source


def _so(content: bytes, path: str = "docs/test.md", sha: str = "abc") -> SourceObject:
    return SourceObject(id=path, path=path, kind="markdown", content_sha256=sha, size=len(content), content=content)


MD_OK = """---
title: Mi Documento
type: manual
tags: [python, test]
related:
  - docs/otro.md
---

Cuerpo del documento con [enlace](docs/destino.md) y [[wiki/objetivo]].
"""


class TestParseSource:
    def test_ok_con_relaciones(self) -> None:
        obj = parse_source(_so(MD_OK.encode()))
        assert isinstance(obj, KnowledgeObject)
        doc = obj.document
        assert doc.frontmatter.title == "Mi Documento"
        assert doc.doc_id == doc_id_from_path("docs/test.md")
        assert doc.doc_type == "manual"
        assert "Cuerpo del documento" in doc.body
        rels = {(r.dst, r.relation) for r in obj.relations}
        assert ("docs/destino.md", "references") in rels
        assert ("wiki/objetivo", "references") in rels
        assert ("docs/otro.md", "references") in rels

    def test_doc_id_desde_frontmatter(self) -> None:
        raw = """---
title: T
type: note
id: custom-id
---

cuerpo
"""
        obj = parse_source(_so(raw.encode()))
        assert obj.document.doc_id == "custom-id"

    def test_empty_body_ke005(self) -> None:
        err = parse_source(_so(b"   "))
        assert isinstance(err, CompileError)
        assert err.code == "KE005"

    def test_content_vacio_ke005(self) -> None:
        err = parse_source(_so(b""))
        assert isinstance(err, CompileError)
        assert err.code == "KE005"

    def test_yaml_invalido_ke006(self) -> None:
        raw = "---\ntitle: [mal\n---\ncuerpo"
        err = parse_source(_so(raw.encode()))
        assert isinstance(err, CompileError)
        assert err.code == "KE006"

    def test_sin_title_ke001(self) -> None:
        raw = "---\ntype: note\n---\ncuerpo"
        err = parse_source(_so(raw.encode()))
        assert isinstance(err, CompileError)
        assert err.code == "KE001"

    def test_sin_type_ke002(self) -> None:
        raw = "---\ntitle: T\n---\ncuerpo"
        err = parse_source(_so(raw.encode()))
        assert isinstance(err, CompileError)
        assert err.code == "KE002"

    def test_utf8_invalido_ke202(self) -> None:
        err = parse_source(_so(b"\xff\xfe\x00"))
        assert isinstance(err, CompileError)
        assert err.code == "KE202"

    def test_sin_frontmatter_ke001(self) -> None:
        err = parse_source(_so(b"cuerpo sin frontmatter"))
        assert isinstance(err, CompileError)
        assert err.code == "KE001"

    def test_frontmatter_escalar(self) -> None:
        raw = "---\n42\n---\ncuerpo"
        err = parse_source(_so(raw.encode()))
        assert isinstance(err, CompileError)
        assert err.code == "KE001"

    def test_frontmatter_vacio(self) -> None:
        raw = "---\n---\ncuerpo"
        err = parse_source(_so(raw.encode()))
        assert isinstance(err, CompileError)
        assert err.code == "KE001"


class TestRelaciones:
    def test_sin_relaciones(self) -> None:
        raw = "---\ntitle: T\ntype: note\n---\n\ncuerpo simple"
        obj = parse_source(_so(raw.encode()))
        assert obj.relations == ()

    def test_enlace_a_si_mismo_ignorado(self) -> None:
        raw = "---\ntitle: T\ntype: note\n---\n\n[yo](docs/test.md)"
        obj = parse_source(_so(raw.encode(), path="docs/test.md"))
        assert obj.relations == ()

    def test_ancla_descartada(self) -> None:
        raw = "---\ntitle: T\ntype: note\n---\n\n[texto](docs/destino.md#seccion)"
        obj = parse_source(_so(raw.encode()))
        assert ("docs/destino.md", "references") in {(r.dst, r.relation) for r in obj.relations}

    def test_duplicados_eliminados(self) -> None:
        raw = "---\ntitle: T\ntype: note\n---\n\n[a](docs/x.md) y [b](docs/x.md) y [[docs/x.md]]"
        obj = parse_source(_so(raw.encode()))
        rels = [(r.src, r.dst) for r in obj.relations]
        assert rels.count(("docs/test.md", "docs/x.md")) == 1

    def test_related_no_lista(self) -> None:
        raw = "---\ntitle: T\ntype: note\nrelated: nope\n---\ncuerpo"
        obj = parse_source(_so(raw.encode()))
        assert obj.relations == ()

    def test_wiki_con_alias(self) -> None:
        raw = "---\ntitle: T\ntype: note\n---\n\n[[docs/destino|alias]]"
        obj = parse_source(_so(raw.encode()))
        assert ("docs/destino", "references") in {(r.dst, r.relation) for r in obj.relations}
