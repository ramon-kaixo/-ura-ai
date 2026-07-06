"""Parser — Markdown SourceObject → KnowledgeObject.

Pipeline: SourceObject (con content bytes) → parse frontmatter → extract body → discover relations

Nunca escribe SQLite.
Nunca valida (eso es C3).
Nunca toca el filesystem — recibe todo desde SourceObject.
Solo transforma.
"""

from __future__ import annotations

import re

import yaml

from knowledge.engine.models import (
    CompileError,
    Document,
    Frontmatter,
    KnowledgeObject,
    Relation,
    SourceObject,
    doc_id_from_path,
)

_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_WIKI_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_ID_ALLOWED = re.compile(r"^[a-zA-Z0-9_\-/\.]+$")


def _extract_frontmatter(raw: str) -> tuple[dict | None, str, str | None]:
    """Extrae frontmatter YAML y body de un string Markdown.

    Retorna (frontmatter_dict, body, error_code) donde error_code es
    KE006 si el YAML es inválido, None si ok.
    """
    m = _FM_PATTERN.match(raw)
    if not m:
        return None, raw.strip(), None

    yaml_text = m.group(1)
    body = raw[m.end() :].strip()

    try:
        fm = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return None, body, "KE006"

    if not isinstance(fm, dict):
        return {}, body, None

    return fm, body, None


def _discover_relations(body: str, source_path: str) -> list[Relation]:
    """Descubre relaciones desde enlaces Markdown y wikilinks en el body.

    Markdown: [text](path) → Relation(src=source_path, dst=path, relation='references')
    Wiki: [[path]] → Relation(src=source_path, dst=path, relation='references')
    """
    relations: list[Relation] = []
    seen: set[tuple[str, str]] = set()

    for match in _LINK_PATTERN.finditer(body):
        dst = match.group(2).split("#")[0].strip()
        if dst and dst != source_path and (source_path, dst) not in seen:
            seen.add((source_path, dst))
            relations.append(Relation(src=source_path, dst=dst, relation="references"))

    for match in _WIKI_PATTERN.finditer(body):
        dst = match.group(1).strip()
        if dst and dst != source_path and (source_path, dst) not in seen:
            seen.add((source_path, dst))
            relations.append(Relation(src=source_path, dst=dst, relation="references"))

    return relations


def parse_source(so: SourceObject) -> KnowledgeObject | CompileError:
    """Parsea un SourceObject → KnowledgeObject.

    Recibe SourceObject con contenido en so.content (bytes).
    NUNCA abre archivos — elimina el TOCTOU entre scanner y parser.

    Retorna KnowledgeObject si el parseo es exitoso.
    Retorna CompileError si hay un error (frontmatter inválido, etc.).
    """
    try:
        raw = so.content.decode("utf-8")
    except UnicodeDecodeError:
        return CompileError(
            code="KE202",
            document=so.path,
            stage="parser",
            message=f"No se pudo decodificar UTF-8: {so.path}",
            category="permanent",
        )

    if not raw.strip():
        return CompileError(
            code="KE005", document=so.path, stage="parser", message=f"Documento vacío: {so.path}", category="permanent"
        )

    fm_dict, body, err_code = _extract_frontmatter(raw)

    if err_code == "KE006":
        return CompileError(
            code="KE006",
            document=so.path,
            stage="parser",
            message=f"Frontmatter inválido en {so.path}",
            category="permanent",
        )

    frontmatter = Frontmatter.from_dict(fm_dict) if fm_dict else Frontmatter()

    if not frontmatter.title:
        return CompileError(
            code="KE001",
            document=so.path,
            stage="parser",
            message=f"Documento sin title: {so.path}",
            category="permanent",
        )

    if not frontmatter.doc_type:
        return CompileError(
            code="KE002",
            document=so.path,
            stage="parser",
            message=f"Documento sin type: {so.path}",
            category="permanent",
        )

    doc_id = fm_dict.get("id", doc_id_from_path(so.path)) if fm_dict else doc_id_from_path(so.path)

    doc = Document(
        doc_id=doc_id,
        doc_type=frontmatter.doc_type,
        path=so.path,
        content_sha256=so.content_sha256,
        frontmatter=frontmatter,
        body=body,
    )

    relations = _discover_relations(body, so.path)
    extra_rels = frontmatter.extra.get("related", [])
    if isinstance(extra_rels, list):
        seen_rels = {(r.src, r.dst) for r in relations}
        for rel in extra_rels:
            if isinstance(rel, str) and (so.path, rel) not in seen_rels:
                seen_rels.add((so.path, rel))
                relations.append(Relation(src=so.path, dst=rel, relation="references"))

    return KnowledgeObject(document=doc, relations=tuple(relations))
