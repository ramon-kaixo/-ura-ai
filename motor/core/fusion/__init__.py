"""Knowledge Fusion (F25).

Fusión multi-documento, resolución de conflictos, detección de
contradicciones y consolidación de fuentes.

API Classification:
- 🟢 ESTABLE: FusionPipeline, FusionResult, FusionContext, KnowledgeFact,
    Fact, FactVersion, FactIndex, FactHistory, PipelineStage, BaseStage,
    EntityResolver, ConflictResolver, KnowledgeMerger, SourceScorer,
    ChangeDetector, MemoryCandidateSelector
- 🟡 ADVANCED: FusionConfig, FusionRegistry, FusionProvenance,
    StageProvenance, Conflict, ConflictGraph, EvidenceSet,
    ResolvedEntity, SourceScore, KnowledgeClaim, KnowledgeDelta,
    FactTombstone, VersionState, ContextBuilder
- 🔵 INTERNA: make_claim_id, make_fact_id, make_version_id,
    make_conflict_id, normalize_identity, FactHistory
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


def run_fusion_on_claims(claims: list, semantic_db: str = "", correlation_id: str = "") -> int:
    """Ejecuta fusión sobre KnowledgeClaims y persiste en memoria semántica + F26.

    Etapas: entity resolution → merge → bridge a SemanticFact →
    SemanticMemoryStore → F26 MemoryEntry.

    Args:
        claims: KnowledgeClaims producidos por KE compile.
        semantic_db: Ruta opcional para persistir SemanticMemoryStore.
        correlation_id: ID de correlación del compile que originó los claims.

    Retorna el número de facts producidos.
    """
    import time as _time

    from motor.core.fusion.models import FusionContext, FusionProvenance
    from motor.core.fusion.stages.entity_resolver import ContextualEntityResolver, EntityResolutionStage
    from motor.core.fusion.stages.merger import KnowledgeMergerStage, SimpleKnowledgeMerger

    context = FusionContext(claims=list(claims), provenance=FusionProvenance())
    er_stage = EntityResolutionStage(resolver=ContextualEntityResolver())
    context = er_stage.execute(context)

    merger_stage = KnowledgeMergerStage(merger=SimpleKnowledgeMerger())
    context = merger_stage.execute(context)

    facts = context.facts or []
    if not facts:
        return 0

    from motor.core.fusion.bridge import knowledge_fact_to_semantic_fact
    from motor.intelligence.memory.semantic import SemanticFact, SemanticMemoryStore
    from motor.memory import FactRef, Memory, MemoryEntry, MemoryEventType, MemoryMetadata, make_entry_id

    store = SemanticMemoryStore(persist_path=semantic_db or None)
    fact_refs: list[tuple] = []
    for kf in facts:
        d = knowledge_fact_to_semantic_fact(kf)
        sf = SemanticFact(**d)
        store.store(sf)
        fact_refs.append((kf.id, d.get("version", 1), kf.subject, kf.predicate, kf.object))

    memory = Memory()
    refs = tuple(
        FactRef(fact_id=fid, version_id=f"v{ver}", subject=subj, predicate=pred, object=obj)
        for fid, ver, subj, pred, obj in fact_refs
    )
    cid = correlation_id[:16] if correlation_id else ""
    entry = MemoryEntry(
        entry_id=make_entry_id("fusion", [r.version_id for r in refs], _time.time()),
        timestamp=_time.time(),
        fact_refs=refs,
        source="knowledge_engine",
        event_type=MemoryEventType.FACT_ADDED,
        metadata=MemoryMetadata(
            pipeline_version="1.0.0",
            fact_count=len(facts),
            created_by=f"compile:{cid}" if cid else "compile",
        ),
    )
    memory.append(entry)

    return len(facts)


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
