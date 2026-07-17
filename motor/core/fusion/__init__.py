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
from motor.core.fusion.config import FusionConfig
from motor.core.fusion.engine import FusionPipeline, FusionStage
from motor.core.fusion.models import (
    Conflict,
    ConflictGraph,
    ConflictType,
    EvidenceSet,
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
    make_claim_id,
    make_conflict_id,
    make_fact_id,
)
from motor.core.fusion.registry import FusionRegistry

__all__ = [
    "ChangeDetector",
    "Conflict",
    "ConflictGraph",
    "ConflictResolver",
    "ConflictType",
    "EntityResolver",
    "EvidenceSet",
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
    "make_claim_id",
    "make_conflict_id",
    "make_fact_id",
]
