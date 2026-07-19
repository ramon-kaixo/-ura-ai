"""Domain models for the Knowledge Engine.

Toda la lógica trabaja sobre estos objetos, nunca sobre diccionarios.
Todos los modelos de dominio son frozen (inmutables) por diseño.

content_sha256:
  - Algoritmo: SHA-256
  - Encoding: UTF-8 (sin BOM)
  - Saltos de línea: LF (no CRLF)
  - Contenido: archivo completo (no normalizado, no filtrado)
  - Ejemplo: hashlib.sha256(path.read_bytes()).hexdigest()
  - Este contrato es inmutable. No cambiar nunca.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Literal
from typing import final as _final

from knowledge.engine._compat import StrEnum
from knowledge.engine.migrations import SCHEMA_VERSION
from knowledge.engine.ontology import (  # noqa: F401 — Capa 11 asset model
    AssetRelationship,
    AssetSource,
    AssetType,
    KnowledgeAsset,
)

if TYPE_CHECKING:
    from pathlib import Path


def doc_id_from_path(path: str) -> str:
    """Deterministic doc_id from relative path.

    Usa SHA-256(path) → 12 hex chars.
    Elimina colisiones entre 'docs/test' y 'docs.test'.
    El id: explícito en frontmatter siempre tiene prioridad.
    """
    p = path.replace("\\", "/").encode("utf-8")
    return hashlib.sha256(p).hexdigest()[:12]


# ── Compile Stage state machine ──────────────────────────────────────────


# ── Type aliases ──────────────────────────────────────────────────────────

JobStatus: Final = Literal["pending", "running", "completed", "failed"]
SeverityLevel: Final = Literal["INFO", "WARN", "ERROR"]
AuditAction: Final = Literal["search", "compile", "archive"]
RuleSeverity: Final = Literal["INFO", "WARN", "ERROR"]

# ── Compile Stage state machine ──────────────────────────────────────────


class CompileStage(StrEnum):
    DISCOVERING = "discovering"
    PARSING = "parsing"
    VALIDATING = "validating"
    WRITING = "writing"
    VERIFYING = "verifying"
    SWAPPING = "swapping"
    DONE = "done"
    FAILED = "failed"


# ── Error categorisation ────────────────────────────────────────────────


class ErrorCategory(StrEnum):
    PERMANENT = "permanent"


# ── Snapshot ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceObject:
    """Objeto fuente descubierto por el Scanner.

    El Scanner descubre objetos de conocimiento (no solo .md).
    El kind se determina por extensión: markdown, yaml, json, drawio, etc.
    """

    id: str
    path: str
    kind: str
    content_sha256: str
    size: int
    content: bytes = b""

    @staticmethod
    def kind_for(path: Path) -> str:
        ext = path.suffix.lower()
        return {
            ".md": "markdown",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".drawio": "drawio",
            ".mmd": "mermaid",
            ".svg": "svg",
            ".pdf": "pdf",
        }.get(ext, ext.lstrip(".") if ext else "unknown")


@dataclass(frozen=True)
class Snapshot:
    """Snapshot lógico del árbol source/ al inicio del compile.

    Previene condiciones de carrera: si un archivo cambia entre scanner y writer,
    el snapshot detecta el cambio y aborta el compile.
    """

    sources: tuple[SourceObject, ...]
    taken_at: str

    def has_changed(self, source_dir: Path) -> bool:
        for so in self.sources:
            src = source_dir / so.path
            if not src.exists():
                return True
            current = hashlib.sha256(src.read_bytes()).hexdigest()
            if current != so.content_sha256:
                return True
        return False

    def deleted(self, previous: Snapshot) -> list[SourceObject]:
        """Retorna los SourceObjects que estaban en previous pero no en este snapshot."""
        current_ids = {s.id for s in self.sources}
        return [s for s in previous.sources if s.id not in current_ids]


# ── Domain models ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Frontmatter:
    """Metadata extraído del YAML frontmatter de un documento Markdown."""

    title: str = ""
    doc_type: str = ""
    tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    status: str = "draft"
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Frontmatter:
        return cls(
            title=d.get("title", ""),
            doc_type=d.get("type", d.get("doc_type", "")),
            tags=tuple(d.get("tags", [])),
            aliases=tuple(d.get("aliases", [])),
            status=d.get("status", "draft"),
            extra={k: v for k, v in d.items() if k not in ("title", "type", "doc_type", "tags", "aliases", "status")},
        )

    def to_dict(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "title": self.title,
            "type": self.doc_type,
            "tags": list(self.tags),
            "aliases": list(self.aliases),
            "status": self.status,
        }
        base.update(self.extra)
        return base


@_final
@dataclass(frozen=True)
class Document:
    """Un documento completo del grafo de conocimiento."""

    doc_id: str
    doc_type: str
    path: str
    content_sha256: str
    frontmatter: Frontmatter
    body: str = ""
    semantic: dict[str, Any] = field(default_factory=dict)
    quality: float = 0.0
    confidence: float = 0.0
    embed_hash: str | None = None
    updated_at: str = ""


@dataclass(frozen=True)
class Relation:
    """Relación dirigida entre dos documentos."""

    src: str
    dst: str
    relation: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SyncOperation:
    """Operación pendiente de sincronización vectorial."""

    doc_id: str
    operation: str  # 'upsert' | 'delete'
    run_id: int = 0
    status: str = "pending"
    last_error: str = ""
    attempts: int = 0


MAX_SYNC_ATTEMPTS = 10
HYBRID_RRF_K = 60


@dataclass(frozen=True)
class Chunk:
    """Fragmento de documento para embedding y búsqueda semántica."""

    doc_id: str
    chunk_index: int
    text: str
    doc_type: str = ""
    path: str = ""
    title: str = ""
    embedding: tuple[float, ...] = ()
    chunk_version: str = ""


@dataclass(frozen=True)
class KnowledgeObject:
    """Objeto de conocimiento: un Document + sus Relations salientes."""

    document: Document
    relations: tuple[Relation, ...] = ()


@dataclass(frozen=True)
class GraphNode:
    """Nodo del grafo para visualización/exploración."""

    doc_id: str
    doc_type: str
    title: str
    path: str
    relations: tuple[Relation, ...] = ()


@dataclass(frozen=True)
class GraphEdge:
    """Arista del grafo para visualización/exploración."""

    src: str
    dst: str
    relation: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Compile pipeline ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class CompileFeatures:
    """Capacidades del compilador para reproducibilidad."""

    parser_version: str = "0.0.0"
    ontology_v1: bool = False
    embeddings: bool = False
    incremental: bool = False
    source_snapshot: bool = True


@_final
@dataclass(frozen=True)
class CompileOptions:
    """User-facing options for a compile run."""

    source_dir: str = ""
    db_path: str = ""
    compiler_version: str = "0.1.0"
    incremental: bool = False
    valid_types: tuple[str, ...] = ()
    max_parse_size: int = 10_485_760


@dataclass(frozen=True)
class CompileMetadata:
    """Read-only metadata collected during the compile."""

    run_id: int = 0
    source_commit: str = ""
    started_at: str = ""
    schema_version: int = SCHEMA_VERSION
    features: CompileFeatures = field(default_factory=CompileFeatures)
    correlation_id: str = ""


@dataclass(frozen=True)
class CompileContext:
    """Contexto inmutable compartido por todo el pipeline del compile.

    Cada etapa (scanner → parser → validator → writer) recibe el mismo contexto.
    """

    metadata: CompileMetadata = field(default_factory=CompileMetadata)
    options: CompileOptions = field(default_factory=CompileOptions)
    snapshot: Snapshot | None = None
    stage: CompileStage = CompileStage.DISCOVERING
    errors: tuple[CompileError, ...] = ()
    warnings: tuple[CompileError, ...] = ()


# ── DTOs ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CompileError:
    """Error o warning de compilación, asociado a un código KE0xx."""

    code: str
    document: str = ""
    stage: str = ""
    message: str = ""
    line: int = 0
    column: int = 0
    category: str = "permanent"


@_final
@dataclass(frozen=True)
class CompileResult:
    """Resultado de una compilación completa."""

    success: bool
    graph_version: int
    source_commit: str
    compiler_version: str
    documents_total: int
    documents_changed: int
    run_id: int = 0
    errors: tuple[CompileError, ...] = ()
    warnings: tuple[CompileError, ...] = ()
    duration_ms: float = 0.0
    stage: str = ""


@_final
@dataclass(frozen=True)
class SearchResult:
    """Resultado de búsqueda con score."""

    doc_id: str
    score: float
    title: str = ""
    snippet: str = ""
    doc_type: str = ""
    document: Document | None = None


@dataclass(frozen=True)
class ValidationResult:
    """Resultado de validación de un documento."""

    valid: bool
    errors: tuple[CompileError, ...] = ()
    warnings: tuple[CompileError, ...] = ()


# ── Política retención ───────────────────────────────────────────────────

COMPILE_ERRORS_RETENTION_RUNS = 100
MAX_PARSE_SIZE = 10_485_760
MAX_CHUNK_WORDS = 500
CHUNK_OVERLAP_WORDS = 50

# ── Archival ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ArchiveManifest:
    """Manifiesto de un archive del Knowledge Engine.

    Cada archive contiene source (git bundle) o vectores (Qdrant dump).
    El grafo (kg_*) NO se archiva: se regenera desde source vía ke compile.
    """

    version: str = "1.0"
    kind: str = "source"  # "source" | "vectors" | "cold"
    source_commit: str = ""
    created_at: str = ""
    archive_path: str = ""
    compressed_size: int = 0
    uncompressed_size: int = 0
    content_sha256: str = ""
    file_count: int = 0  # solo para source
    model_id: str = ""  # solo para vectors
    embed_dim: int = 0  # solo para vectors
    retention_days: int = 90

    @classmethod
    def from_dict(cls, data: dict) -> ArchiveManifest:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


ARCHIVE_RETENTION_DAYS: dict[str, int] = {
    "source": 90,  # warm: source bundles se mantienen 90 días
    "vectors": 90,  # warm: dumps de Qdrant se mantienen 90 días
    "cold": 365,  # cold: backup remoto completo se mantiene 1 año
}


# ── Auditoría ─────────────────────────────────────────────────────────────


@_final
@dataclass(frozen=True)
class AuditEvent:
    """Evento de auditoría del Knowledge Engine.

    Diseñado para serialización NDJSON (un evento por línea).
    Todos los campos son serializables a JSON sin pérdida.
    """

    action: str  # "read" | "compile" | "archive" | "search" | …
    actor: str  # "reader" | "compiler" | "archiver" | "cli" | …
    entity_type: str  # "document" | "graph" | "archive" | …
    entity_id: str  # doc_id, commit hash, archive manifest, …
    result: str  # "success" | "failure"
    correlation_id: str
    timestamp: str  # ISO 8601: datetime.now(UTC).isoformat()
    metadata: dict[str, Any] = field(default_factory=dict)
