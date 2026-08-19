"""Tests de cobertura para knowledge/engine/validator.py."""

from __future__ import annotations

from knowledge.engine.models import (
    CompileError,
    Document,
    Frontmatter,
    KnowledgeObject,
    Relation,
)
from knowledge.engine.validator import (
    DEPRECATED_FIELDS,
    VALID_DOC_TYPES,
    VALID_STATUSES,
    _check_duplicados,
    _construir_lookups,
    _validar_campos_obsoletos,
    _validar_doc_type,
    _validar_relaciones,
    _validar_tags_aliases,
    _validar_warnings_core,
    _warn_rango,
    validate_batch,
    validate_knowledge_object,
)


def _doc(
    doc_id: str = "a1",
    doc_type: str = "doc",
    path: str | None = None,
    status: str = "draft",
    tags: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    body: str = "Contenido suficientemente largo para el validador de conocimiento.",
    quality: float = 0.8,
    confidence: float = 0.9,
    extra: dict | None = None,
) -> Document:
    return Document(
        doc_id=doc_id,
        doc_type=doc_type,
        path=path or f"docs/{doc_id}.md",
        content_sha256="sha",
        frontmatter=Frontmatter(
            title="T", doc_type=doc_type, tags=tags, aliases=aliases, status=status, extra=extra or {}
        ),
        body=body,
        quality=quality,
        confidence=confidence,
    )


def _obj(doc: Document, relations: tuple[Relation, ...] = ()) -> KnowledgeObject:
    return KnowledgeObject(document=doc, relations=relations)


def _rel(dst: str, relation: str = "references") -> Relation:
    return Relation(src="a1", dst=dst, relation=relation)


def test_validacion_ok() -> None:
    vr = validate_knowledge_object(_obj(_doc()))
    assert vr.valid is True
    assert vr.errors == ()
    assert vr.warnings == ()


def test_doc_type_invalido() -> None:
    vr = validate_knowledge_object(_obj(_doc(doc_type="xxx")))
    assert vr.valid is False
    codes = [e.code for e in vr.errors]
    assert "KE003" in codes


def test_doc_type_vacio() -> None:
    vr = validate_knowledge_object(_obj(_doc(doc_type="")))
    assert "KE003" in [e.code for e in vr.errors]


def test_valid_types_personalizado() -> None:
    vr = validate_knowledge_object(_obj(_doc(doc_type="x")), valid_types=frozenset({"x"}))
    assert vr.valid is True


def test_doc_id_invalido() -> None:
    vr = validate_knowledge_object(_obj(_doc(doc_id="  ")))
    assert "KE009" in [w.code for w in vr.warnings]


def test_status_no_estandar() -> None:
    vr = validate_knowledge_object(_obj(_doc(status="pending")))
    assert "KE009" in [w.code for w in vr.warnings]


def test_quality_fuera_de_rango() -> None:
    vr = validate_knowledge_object(_obj(_doc(quality=1.5)))
    assert "KE009" in [w.code for w in vr.warnings]
    vr2 = validate_knowledge_object(_obj(_doc(confidence=-0.1)))
    assert "KE009" in [w.code for w in vr2.warnings]


def test_body_corto() -> None:
    vr = validate_knowledge_object(_obj(_doc(body="corto")))
    assert "KE009" in [w.code for w in vr.warnings]


def test_body_vacio_sin_warning() -> None:
    vr = validate_knowledge_object(_obj(_doc(body="")))
    assert "KE009" not in [w.code for w in vr.warnings]


def test_tags_invalidos() -> None:
    vr = validate_knowledge_object(_obj(_doc(tags=("ok", "", 3))))
    assert "KE009" in [w.code for w in vr.warnings]


def test_aliases_invalidos() -> None:
    vr = validate_knowledge_object(_obj(_doc(aliases=("", "  "))))
    assert "KE009" in [w.code for w in vr.warnings]


def test_campos_obsoletos() -> None:
    vr = validate_knowledge_object(_obj(_doc(extra={"category": "x", "author": "y"})))
    codes = [w.code for w in vr.warnings]
    assert codes.count("KE204") == 2


def test_warn_rango() -> None:
    w: list[CompileError] = []
    _warn_rango(w, "p", "x", 0.5, 0.0, 1.0)
    assert w == []
    _warn_rango(w, "p", "x", 1.5, 0.0, 1.0)
    assert len(w) == 1
    assert w[0].code == "KE009"
    assert "x fuera de rango" in w[0].message


def test_validar_doc_type_directo() -> None:
    errs: list[CompileError] = []
    _validar_doc_type(_doc(doc_type="adr"), VALID_DOC_TYPES, errs)
    assert errs == []


def test_validar_warnings_core_directo() -> None:
    w: list[CompileError] = []
    _validar_warnings_core(_doc(), w)
    assert w == []


def test_validar_tags_aliases_directo() -> None:
    w: list[CompileError] = []
    _validar_tags_aliases(_doc(tags=("a",), aliases=("b",)), w)
    assert w == []


def test_validar_campos_obsoletos_directo() -> None:
    w: list[CompileError] = []
    _validar_campos_obsoletos(_doc(extra={"version": 1}), w)
    assert len(w) == 1
    assert "version" in w[0].message


def test_batch_ok() -> None:
    objs = [_obj(_doc("a1")), _obj(_doc("a2"))]
    valid, errors, warnings = validate_batch(objs)
    assert len(valid) == 2
    assert errors == []
    assert warnings == []


def test_batch_excluye_invalidos() -> None:
    objs = [_obj(_doc("a1")), _obj(_doc("a2", doc_type="bad"))]
    valid, errors, _warnings = validate_batch(objs)
    assert len(valid) == 1
    assert "KE003" in [e.code for e in errors]


def test_batch_relacion_inexistente() -> None:
    objs = [_obj(_doc("a1"), relations=(_rel("zz"),))]
    valid, errors, _warnings = validate_batch(objs)
    assert len(valid) == 1
    assert "KE004" in [e.code for e in errors]


def test_batch_relacion_dedup() -> None:
    objs = [
        _obj(_doc("a1"), relations=(_rel("zz"), _rel("zz", "depends"))),
    ]
    _valid, errors, _warnings = validate_batch(objs)
    assert [e.code for e in errors].count("KE004") == 1


def test_batch_relacion_existente() -> None:
    objs = [_obj(_doc("a1"), relations=(_rel("a2"),)), _obj(_doc("a2"))]
    _valid, errors, _warnings = validate_batch(objs)
    assert "KE004" not in [e.code for e in errors]


def test_batch_alias_resuelve_relacion() -> None:
    objs = [_obj(_doc("a1"), relations=(_rel("alias-x"),)), _obj(_doc("a2", aliases=("alias-x",)))]
    _valid, errors, _warnings = validate_batch(objs)
    assert "KE004" not in [e.code for e in errors]


def test_batch_ids_duplicados() -> None:
    objs = [_obj(_doc("dup")), _obj(_doc("dup"))]
    _valid, errors, _warnings = validate_batch(objs)
    assert "KE101" in [e.code for e in errors]


def test_batch_paths_duplicados() -> None:
    objs = [_obj(_doc("a1", path="docs/mismo.md")), _obj(_doc("a2", path="docs/mismo.md"))]
    _valid, _errors, warnings = validate_batch(objs)
    assert "KE007" in [w.code for w in warnings]


def test_construir_lookups() -> None:
    objs = [_obj(_doc("a1", aliases=("al1", "  "))), _obj(_doc("a2"))]
    doc_count, path_count, known = _construir_lookups(objs)
    assert doc_count["a1"] == 1
    assert path_count["docs/a1.md"] == 1
    assert "al1" in known


def test_validar_relaciones_directo() -> None:
    errs: list[CompileError] = []
    reported: set[tuple[str, str]] = set()
    _validar_relaciones(_obj(_doc("a1"), relations=(_rel("x"),)), {"a1"}, reported, errs)
    assert len(errs) == 1
    assert errs[0].code == "KE004"


def test_check_duplicados_directo() -> None:
    errs: list[CompileError] = []
    warns: list[CompileError] = []
    _check_duplicados({"dup": 2, "": 3, "ok": 1}, {"p": 2}, errs, warns)
    assert "KE101" in [e.code for e in errs]
    assert "KE007" in [w.code for w in warns]


def test_constantes() -> None:
    assert "doc" in VALID_DOC_TYPES
    assert "draft" in VALID_STATUSES
    assert "category" in DEPRECATED_FIELDS
