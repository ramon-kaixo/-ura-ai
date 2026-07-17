"""Modelos de datos del módulo Knowledge Fusion (F25).

Reglas:
- KnowledgeFact es inmutable (frozen). Si cambia → nueva versión.
- KnowledgeClaim es mutable (se enriquece durante normalización/scoring).
- IDs deterministas (SHA-256), no UUIDs aleatorios.
- Sin lógica de negocio en modelos. Toda inteligencia en ABCs.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.core.web.citation.citation import Evidence
    from motor.core.web.models import WebDocument


# ── Normalización canónica de identidad ───


def normalize_identity(text: str) -> str:
    """Normalización canónica para identidad de hechos.

    Única implementación permitida. Todos los puntos donde se calcule
    un fact_id deben usar exactamente esta función.
    - lowercase + strip
    - espacios múltiples → simple
    - puntuación no esencial eliminada
    - NO resuelve sinónimos (CEO → Chief Executive Officer)
    - NO resuelve entidades (Apple → E0001)
    """
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


# ── IDs deterministas ─────────────────────


def make_claim_id(evidence_id: str, text: str) -> str:
    raw = f"{evidence_id}:{text.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def make_fact_id(
    subject: str,
    predicate: str,
    obj: str,
) -> str:
    """ID determinista de Fact.

    Usa normalize_identity() canónica. version NO participa en la identidad.
    """
    raw = (
        f"{normalize_identity(subject)}:"
        f"{normalize_identity(predicate)}:"
        f"{normalize_identity(obj)}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def make_version_id(fact_id: str, timestamp: float, content_hash: str) -> str:
    """ID determinista de versión.

    Independiente del orden de inserción en FactHistory.
    NO participan: ordinal, current, estado temporal del sistema.
    """
    raw = f"{fact_id}:{int(timestamp)}:{content_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def make_conflict_id(
    claim_a_id: str,
    claim_b_id: str,
    conflict_type: str,
) -> str:
    raw = f"{claim_a_id}:{claim_b_id}:{conflict_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── Enums ──────────────────────────────────


class ConflictType(StrEnum):
    CONTRADICTION = "contradiction"
    TEMPORAL_UPDATE = "temporal_update"
    DIFFERENT_GRANULARITY = "different_granularity"
    DIFFERENT_SCOPE = "different_scope"
    OPINION = "opinion"


class ResolutionStatus(StrEnum):
    """Estado de resolución de una entidad."""

    RESOLVED = "resolved"
    UNKNOWN = "unknown"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"


class VersionState(StrEnum):
    """Estado de una FactVersion dentro de FactHistory.

    Mutuamente excluyentes. Una versión solo puede estar en un estado.
    """

    CURRENT = "current"
    SUPERSEDED = "superseded"
    ROLLED_BACK = "rolled_back"
    TOMBSTONE = "obsolete"
    DELETED = "deleted"


# ── Fact (identidad) ──────────────────────


@dataclass(frozen=True)
class Fact:
    """Identidad inmatable de un hecho de conocimiento.

    - Dos Facts son el mismo hecho si tienen el mismo fact_id.
    - fact_id se deriva exclusivamente de (normalized subject, predicate, object).
    - Ningún otro atributo participa en la identidad.
    - Un Fact no tiene confianza, evidencia ni versión — solo identidad.
    """

    fact_id: str
    subject: str
    predicate: str
    object: str


# ── FactTombstone ─────────────────────────


@dataclass(frozen=True)
class FactTombstone:
    """Marcador de eliminación lógica de un Fact.

    Participa en FactIndex hasta DELETE físico.
    """

    fact_id: str
    removed_at: float
    reason: str
    version_id: str | None = None


# ── FactVersion (contenido) ───────────────


@dataclass(frozen=True)
class FactVersion:
    """Una versión concreta de un hecho en un instante.

    - Pertenece exactamente a un Fact (vía fact_id). NO existe sin él.
    - Diferentes versiones del mismo Fact comparten fact_id.
    - version_id es independiente del orden de inserción en FactHistory.
    """

    version_id: str
    fact_id: str
    confidence: float
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    provenance: tuple[str, ...] = field(default_factory=tuple)
    created_at: float = 0.0
    supersedes: str | None = None
    state: VersionState = VersionState.CURRENT


# ── ResolvedEntity (salida de EntityResolver) ─


@dataclass
class ResolvedEntity:
    """Entidad resuelta por EntityResolver.

    Contiene metadatos sobre el proceso de resolución: confianza,
    alias detectados, estado explícito y versión del algoritmo.
    """

    entity_id: str
    canonical_name: str
    confidence: float
    status: ResolutionStatus = ResolutionStatus.RESOLVED
    aliases: tuple[str, ...] = ()
    resolver_name: str = ""
    resolver_version: str = ""


# ── SourceScore ────────────────────────────


@dataclass
class SourceScore:
    url: str
    authority: float = 0.0
    freshness: float = 0.0
    corroboration: float = 0.0
    internal_consistency: float = 0.0
    historical_accuracy: float = 0.0
    citation_quality: float = 0.0
    overall: float = 0.0


# ── KnowledgeClaim (mutable) ─────────────


@dataclass
class KnowledgeClaim:
    id: str
    text: str
    confidence: float
    evidence: Evidence | None = None
    source_score: SourceScore | None = None
    normalized_text: str = ""
    subject: str = ""
    predicate: str = ""
    object: str = ""
    created_at: float = field(default_factory=time.time)
    text_id: str = ""


# ── Conflict (mutable: se resuelve) ────────


@dataclass
class Conflict:
    id: str
    claim_a: str
    claim_b: str
    conflict_type: ConflictType = ConflictType.CONTRADICTION
    description: str = ""
    resolved: bool = False
    resolution: str | None = None


# ── ConflictGraph (grafo de conflictos N-arios) ─


@dataclass
class ConflictGraph:
    """Grafo de conflictos entre claims.

    Un claim puede estar en conflicto con múltiples otros claims.
    Este grafo permite:
    - Analizar clusters completos de contradicciones
    - Resolver conflictos encadenados (resolver uno afecta a otros)
    - Detectar patrones de conflicto (circulares, estrella, cadena)
    - Fallback a lista simple para compatibilidad hacia atrás
    """

    edges: list[Conflict] = field(default_factory=list)
    claim_ids: set[str] = field(default_factory=set)

    @property
    def has_conflicts(self) -> bool:
        return len(self.edges) > 0

    @property
    def unresolved_count(self) -> int:
        return sum(1 for e in self.edges if not e.resolved)

    @property
    def unresolved(self) -> list[Conflict]:
        return [e for e in self.edges if not e.resolved]

    def claims_for(self, claim_id: str) -> list[str]:
        """Retorna todos los claim_ids en conflicto con claim_id."""
        related: set[str] = set()
        for e in self.edges:
            if e.claim_a == claim_id:
                related.add(e.claim_b)
            elif e.claim_b == claim_id:
                related.add(e.claim_a)
        return list(related)

    def clusters(self) -> list[set[str]]:
        """Retorna componentes conectados del grafo (algoritmo naive)."""
        visited: set[str] = set()
        components: list[set[str]] = []

        def _dfs(node: str, comp: set[str]) -> None:
            if node in visited:
                return
            visited.add(node)
            comp.add(node)
            for neighbor in self.claims_for(node):
                _dfs(neighbor, comp)

        for cid in self.claim_ids:
            if cid not in visited:
                comp: set[str] = set()
                _dfs(cid, comp)
                if comp:
                    components.append(comp)

        return components

    @classmethod
    def from_edges(cls, edges: list[Conflict]) -> ConflictGraph:
        claim_ids: set[str] = set()
        for e in edges:
            claim_ids.add(e.claim_a)
            claim_ids.add(e.claim_b)
        return cls(edges=list(edges), claim_ids=claim_ids)


# ── KnowledgeFact (inmutable) ──────────────


@dataclass(frozen=True)
class KnowledgeFact:
    id: str
    subject: str
    predicate: str
    object: str
    confidence: float
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    provenance: tuple[str, ...] = field(default_factory=tuple)
    version: int = 1
    created_at: float = field(default_factory=time.time)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    # DEPRECATED: usar FactHistory en lugar de enlaces entre Facts
    # Estos campos se eliminarán cuando FactHistory esté completamente integrado.
    superseded_by: str | None = None
    previous_version: str | None = None


# ── KnowledgeDelta (cambio entre estados) ──


@dataclass
class KnowledgeDelta:
    facts_added: tuple[KnowledgeFact, ...] = field(default_factory=tuple)
    facts_updated: tuple[KnowledgeFact, ...] = field(default_factory=tuple)
    facts_removed: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    conflicts_resolved: int = 0
    conflicts_new: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(
            self.facts_added or self.facts_updated or self.facts_removed
        )


# ── EvidenceSet (claims extraídos) ─────────


@dataclass
class EvidenceSet:
    claims: list[KnowledgeClaim] = field(default_factory=list)
    source_documents: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.claims)


# ── FusionProvenance (reproducibilidad) ────


@dataclass
class FusionProvenance:
    """Metadatos de versión para reproducibilidad de ejecuciones.

    Cada ejecución del pipeline debe poder reconstruirse:
    entrada + pipeline_version + versiones de cada componente
    + config_hash = resultado reproducible.
    """

    pipeline_version: str = ""
    resolver_name: str = ""
    resolver_version: str = ""
    conflict_resolver_name: str = ""
    conflict_resolver_version: str = ""
    merger_name: str = ""
    merger_version: str = ""
    source_scorer_name: str = ""
    source_scorer_version: str = ""
    change_detector_name: str = ""
    change_detector_version: str = ""
    selector_name: str = ""
    selector_version: str = ""
    config_hash: str = ""


# ── StageProvenance (auditoría por etapa) ──


@dataclass
class StageProvenance:
    """Registro de transformación aplicada por una etapa del pipeline.

    Cada etapa deja constancia de qué modificó, permitiendo auditoría
    y depuración en F26/F27.
    """

    stage_name: str
    stage_version: str
    transformer: str
    input_claims: int = 0
    output_claims: int = 0
    timestamp: float = field(default_factory=time.time)


# ── FusionContext (estado interno del pipeline) ─


@dataclass
class FusionContext:
    """Contexto tipado compartido entre etapas del pipeline.

    Reemplaza un dict sin estructura, previniendo errores por
    claves mal escritas y habilitando autocompletado.
    """

    bundle: Any = None
    documents: list[WebDocument] = field(default_factory=list)
    claims: list[KnowledgeClaim] = field(default_factory=list)
    entities: list[ResolvedEntity] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    conflict_graph: ConflictGraph | None = None
    facts: list[KnowledgeFact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)
    provenance: FusionProvenance = field(default_factory=FusionProvenance)
    transforms: list[StageProvenance] = field(default_factory=list)


# ── FusionResult (salida del pipeline) ─────


@dataclass
class FusionResult:
    accepted: tuple[KnowledgeFact, ...] = field(default_factory=tuple)
    rejected: tuple[KnowledgeClaim, ...] = field(default_factory=tuple)
    conflicts: tuple[Conflict, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    statistics: dict[str, Any] = field(default_factory=dict)
    provenance: FusionProvenance = field(default_factory=FusionProvenance)
