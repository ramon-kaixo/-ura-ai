"""Error codes for the Knowledge Engine (KE0xx).

Format: KE<XXX>: <severity> — <description>
Severity: ERROR, WARN, DEPRECATED, INFO
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.engine._compat import StrEnum


class Severity(StrEnum):
    ERROR = "ERROR"
    WARN = "WARN"
    DEPRECATED = "DEPRECATED"
    INFO = "INFO"


@dataclass(frozen=True)
class ErrorCode:
    code: str
    severity: Severity
    title: str
    description: str


# ── Compilation errors (KE0xx) ──────────────────────────────────────────────

KE001 = ErrorCode("KE001", Severity.ERROR, "Missing title", "El frontmatter no contiene campo 'title'")
KE002 = ErrorCode("KE002", Severity.ERROR, "Missing type", "El frontmatter no contiene campo 'type'")
KE003 = ErrorCode("KE003", Severity.ERROR, "Invalid type", "El campo 'type' no es un tipo válido de nodo")
KE004 = ErrorCode("KE004", Severity.ERROR, "Broken relation", "Una relación apunta a un documento que no existe")
KE005 = ErrorCode("KE005", Severity.WARN, "Empty document", "El documento no contiene contenido markdown")
KE006 = ErrorCode("KE006", Severity.ERROR, "Invalid frontmatter", "El frontmatter YAML no se puede parsear")
KE007 = ErrorCode("KE007", Severity.WARN, "Duplicate path", "Dos documentos comparten la misma ruta de source")
KE008 = ErrorCode(
    "KE008",
    Severity.ERROR,
    "Circular dependency",
    "Se ha detectado una dependencia circular en el grafo",
)
KE009 = ErrorCode("KE009", Severity.WARN, "Missing field", "Falta un campo opcional pero recomendado en frontmatter")
KE010 = ErrorCode("KE010", Severity.WARN, "Unused relation", "Una relación no se usa en ningún documento")

# ── FSCK errors (KE1xx) ────────────────────────────────────────────────────

KE101 = ErrorCode("KE101", Severity.ERROR, "Duplicate node ID", "Dos nodos comparten el mismo ID en kg_nodes")
KE102 = ErrorCode("KE102", Severity.ERROR, "Duplicate node path", "Dos nodos comparten la misma ruta en kg_nodes")
KE103 = ErrorCode(
    "KE103",
    Severity.WARN,
    "Repeated content hash",
    "Varios documentos tienen el mismo content_sha256 (duplicado real)",
)
KE104 = ErrorCode("KE104", Severity.WARN, "Orphan node", "Nodo sin ninguna arista entrante ni saliente")
KE105 = ErrorCode("KE105", Severity.ERROR, "Broken edge source", "kg_edges.src no existe en kg_nodes")
KE106 = ErrorCode("KE106", Severity.ERROR, "Broken edge target", "kg_edges.dst no existe en kg_nodes")
KE107 = ErrorCode(
    "KE107",
    Severity.WARN,
    "Ontology inconsistency",
    "Un nodo de ontología tiene parent_id que no existe",
)
KE108 = ErrorCode("KE108", Severity.WARN, "Orphan ontology node", "Nodo de ontología sin aristas y sin hijos")
KE109 = ErrorCode("KE109", Severity.ERROR, "FTS desync", "FTS5 desincronizado con kg_nodes")
KE110 = ErrorCode("KE110", Severity.WARN, "ForeignKey disabled", "PRAGMA foreign_keys no está activado")
KE111 = ErrorCode("KE111", Severity.WARN, "Journal mode", "journal_mode no es WAL recomendado")

# ── Runtime errors (KE2xx) ──────────────────────────────────────────────────

KE201 = ErrorCode(
    "KE201",
    Severity.ERROR,
    "Reader not initialized",
    "KnowledgeReader no tiene conexión a la base de datos",
)
KE202 = ErrorCode("KE202", Severity.ERROR, "Document not found", "El documento solicitado no existe en el grafo")
KE203 = ErrorCode("KE203", Severity.ERROR, "Search failed", "La búsqueda FTS5 falló por error interno")
KE204 = ErrorCode("KE204", Severity.DEPRECATED, "Deprecated field", "Un campo usado está marcado como obsoleto")
KE205 = ErrorCode("KE205", Severity.WARN, "File skipped", "Archivo omitido por exceder MAX_PARSE_SIZE")
KE206 = ErrorCode("KE206", Severity.WARN, "Transient error", "Error transitorio (permiso, E/S) — puede reintentarse")
KE207 = ErrorCode("KE207", Severity.INFO, "Document deleted", "Documento eliminado de source/ desde el último compile")
KE210 = ErrorCode("KE210", Severity.WARN, "Symlink skipped", "Enlace simbólico omitido por seguridad en scanner")

# ── All codes lookup ────────────────────────────────────────────────────────

_ALL_CODES: dict[str, ErrorCode] = {}


def _register(c: ErrorCode) -> None:
    _ALL_CODES[c.code] = c


for _obj in list(locals().values()):
    if isinstance(_obj, ErrorCode):
        _register(_obj)


def lookup(code: str) -> ErrorCode | None:
    return _ALL_CODES.get(code)


def all_codes() -> list[ErrorCode]:
    return sorted(_ALL_CODES.values(), key=lambda c: c.code)
