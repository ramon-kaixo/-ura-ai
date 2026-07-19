"""Validator — valida KnowledgeObjects contra tipos, calidad y ontología.

Pipeline: validate_knowledge_object → validate_batch
Nunca parsea. Nunca escribe SQL.
Solo produce ValidationResult con errores y warnings.
"""

from __future__ import annotations

from knowledge.engine.models import (
    CompileError,
    KnowledgeObject,
    ValidationResult,
)

VALID_DOC_TYPES: frozenset[str] = frozenset(
    {
        "adr",
        "doc",
        "spec",
        "guide",
        "note",
        "reference",
        "tutorial",
        "api",
        "concept",
        "architecture",
    },
)

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "review",
        "published",
        "archived",
        "deprecated",
        "wip",
    },
)

DEPRECATED_FIELDS: frozenset[str] = frozenset(
    {
        "category",
        "author",
        "version",
    },
)

_MIN_BODY_CHARS = 10


def validate_knowledge_object(  # noqa: C901
    obj: KnowledgeObject,
    valid_types: frozenset[str] | None = None,
) -> ValidationResult:
    """Valida un KnowledgeObject individual.

    No requiere contexto global (no conoce otros documentos).
    Retorna ValidationResult con errores (KE003, KE204) y warnings (KE009).
    """
    types = valid_types if valid_types is not None else VALID_DOC_TYPES
    errors: list[CompileError] = []
    warnings: list[CompileError] = []
    doc = obj.document
    path = doc.path

    # KE003: doc_type inválido (incluye string vacío o no-string)
    if not isinstance(doc.doc_type, str) or doc.doc_type not in types:
        errors.append(
            CompileError(
                code="KE003",
                document=path,
                stage="validator",
                message=f"Tipo de documento inválido: '{doc.doc_type}'. Válidos: {sorted(types)}",
            ),
        )

    # KE009: doc_id debe ser string no vacío
    if not isinstance(doc.doc_id, str) or not doc.doc_id.strip():
        warnings.append(
            CompileError(
                code="KE009",
                document=path,
                stage="validator",
                message=f"doc_id inválido (debe ser string no vacío): {doc.doc_id!r}",
            ),
        )

    # KE009: status no estándar
    if doc.frontmatter.status not in VALID_STATUSES:
        warnings.append(
            CompileError(
                code="KE009",
                document=path,
                stage="validator",
                message=f"Status no estándar: '{doc.frontmatter.status}'. Esperado uno de: {sorted(VALID_STATUSES)}",
            ),
        )

    # KE009: quality fuera de rango
    if doc.quality < 0.0 or doc.quality > 1.0:
        warnings.append(
            CompileError(
                code="KE009",
                document=path,
                stage="validator",
                message=f"quality fuera de rango [0.0, 1.0]: {doc.quality}",
            ),
        )

    # KE009: confidence fuera de rango
    if doc.confidence < 0.0 or doc.confidence > 1.0:
        warnings.append(
            CompileError(
                code="KE009",
                document=path,
                stage="validator",
                message=f"confidence fuera de rango [0.0, 1.0]: {doc.confidence}",
            ),
        )

    # KE009: body muy corto
    body_stripped = doc.body.strip()
    if body_stripped and len(body_stripped) < _MIN_BODY_CHARS:
        warnings.append(
            CompileError(
                code="KE009",
                document=path,
                stage="validator",
                message=f"Body muy corto ({len(body_stripped)} chars, mínimo {_MIN_BODY_CHARS})",
            ),
        )

    # KE009: tags inválidos
    for tag in doc.frontmatter.tags:
        if not isinstance(tag, str) or not tag.strip():
            warnings.append(  # noqa: PERF401
                CompileError(
                    code="KE009",
                    document=path,
                    stage="validator",
                    message=f"Tag inválido: {tag!r}",
                ),
            )

    # KE009: aliases inválidos
    for alias in doc.frontmatter.aliases:
        if not isinstance(alias, str) or not alias.strip():
            warnings.append(  # noqa: PERF401
                CompileError(
                    code="KE009",
                    document=path,
                    stage="validator",
                    message=f"Alias inválido: {alias!r}",
                ),
            )

    # KE204: campos obsoletos
    for field in DEPRECATED_FIELDS:
        if field in doc.frontmatter.extra:
            warnings.append(  # noqa: PERF401
                CompileError(
                    code="KE204",
                    document=path,
                    stage="validator",
                    message=f"Campo obsoleto en frontmatter: '{field}'",
                ),
            )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_batch(  # noqa: C901
    objects: list[KnowledgeObject],
    valid_types: frozenset[str] | None = None,
) -> tuple[list[KnowledgeObject], list[CompileError], list[CompileError]]:
    """Valida un batch completo de KnowledgeObjects.

    Incluye chequeos cross-document:
      - KE004: relaciones que apuntan a documentos inexistentes
      - KE007: paths duplicados entre documentos (warning, no excluye)
      - KE101: IDs duplicados entre documentos

    Retorna (válidos, errores, warnings).
    Los objetos con errores KE003 se excluyen del batch válido.
    """
    types = valid_types if valid_types is not None else VALID_DOC_TYPES
    errors: list[CompileError] = []
    warnings: list[CompileError] = []
    valid: list[KnowledgeObject] = []

    # Build lookup structures
    doc_id_count: dict[str, int] = {}
    path_count: dict[str, int] = {}
    known_ids: set[str] = set()
    for obj in objects:
        did = obj.document.doc_id
        doc_id_count[did] = doc_id_count.get(did, 0) + 1
        path_count[obj.document.path] = path_count.get(obj.document.path, 0) + 1
        known_ids.add(did)
        for alias in obj.document.frontmatter.aliases:
            if isinstance(alias, str) and alias.strip():
                known_ids.add(alias)

    # Track relations already reported per (doc, dst) to dedup KE004
    reported_ke004: set[tuple[str, str]] = set()

    for obj in objects:
        vr = validate_knowledge_object(obj, types)
        errors.extend(vr.errors)
        warnings.extend(vr.warnings)

        if vr.errors:
            continue

        doc_id = obj.document.doc_id
        path = obj.document.path
        for rel in obj.relations:
            dst = rel.dst
            if dst not in known_ids and (path, dst) not in reported_ke004:
                reported_ke004.add((path, dst))
                errors.append(
                    CompileError(
                        code="KE004",
                        document=path,
                        stage="validator",
                        message=f"Relación '{rel.relation}' apunta a documento inexistente: '{dst}' (desde {doc_id})",
                    ),
                )

        valid.append(obj)

    # Cross-document checks
    for did, count in doc_id_count.items():
        if count > 1 and isinstance(did, str) and did.strip():
            errors.append(
                CompileError(
                    code="KE101",
                    document="",
                    stage="validator",
                    message=f"ID duplicado entre documentos: '{did}' aparece {count} veces",
                ),
            )

    for path_str, count in path_count.items():
        if count > 1:
            warnings.append(
                CompileError(
                    code="KE007",
                    document=path_str,
                    stage="validator",
                    message=f"Path duplicado: '{path_str}' aparece {count} veces",
                ),
            )

    return valid, errors, warnings
