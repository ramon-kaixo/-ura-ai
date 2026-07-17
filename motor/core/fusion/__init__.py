"""Knowledge Fusion (F25).

Fusión multi-documento, resolución de conflictos, detección de
contradicciones y consolidación de fuentes.

F25 consume los CitationBundle y Evidence generados por F24 y produce
KnowledgeFact con trazabilidad completa.
"""

from __future__ import annotations

from motor.core.fusion.base import (
    ChangeDetector,
    ConflictResolver,
    EntityResolver,
    FusionEngine,
    KnowledgeMerger,
    MemoryCandidateSelector,
    PipelineStage,
    SourceScorer,
)
from motor.core.fusion.bridge import fact_version_to_semantic_fact, knowledge_fact_to_semantic_fact
from motor.core.fusion.config import FusionConfig
from motor.core.fusion.context_builder import ContextBuilder
from motor.core.fusion.engine import FusionPipeline, FusionStage
from motor.core.fusion.fact_index import FactIndex
from motor.core.fusion.models import (
    Conflict,
    ConflictGraph,
    ConflictType,
    EvidenceSet,
    Fact,
    FactTombstone,
    FactVersion,
    FusionContext,
    FusionProvenance,
    FusionResult,
    KnowledgeClaim,
    KnowledgeDelta,
    KnowledgeFact,
    ResolutionStatus,
    ResolvedEntity,
    SourceScore,
    StageProvenance,
    VersionState,
    make_claim_id,
    make_conflict_id,
    make_fact_id,
    make_version_id,
    normalize_identity,
)
from motor.core.fusion.registry import FusionRegistry

__all__ = [
    "ChangeDetector",
    "Conflict",
    "ConflictGraph",
    "ConflictResolver",
    "ConflictType",
    "ContextBuilder",
    "EntityResolver",
    "EvidenceSet",
    "Fact",
    "FactIndex",
    "FactTombstone",
    "FactVersion",
    "FusionConfig",
    "FusionContext",
    "FusionEngine",
    "FusionPipeline",
    "FusionProvenance",
    "FusionRegistry",
    "FusionResult",
    "FusionStage",
    "KnowledgeClaim",
    "KnowledgeDelta",
    "KnowledgeFact",
    "KnowledgeMerger",
    "MemoryCandidateSelector",
    "PipelineStage",
    "ResolutionStatus",
    "ResolvedEntity",
    "SourceScore",
    "SourceScorer",
    "StageProvenance",
    "VersionState",
    "fact_version_to_semantic_fact",
    "knowledge_fact_to_semantic_fact",
    "make_claim_id",
    "make_conflict_id",
    "make_fact_id",
    "make_version_id",
    "normalize_identity",
]
