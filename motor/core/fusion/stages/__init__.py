"""Implementaciones concretas de PipelineStage para F25-B2/B3."""

from motor.core.fusion.stages.conflict_detection import (
    ConflictDetectionStage,
    NaiveConflictResolver,
)
from motor.core.fusion.stages.delta import BasicChangeDetector, KnowledgeDeltaStage
from motor.core.fusion.stages.entity_resolver import (
    CachePolicy,
    ContextualEntityResolver,
    EntityDef,
    EntityRegistry,
    EntityResolutionStage,
    KeywordScorer,
    LRUCache,
    RuleBasedEntityResolver,
    ScoringStrategy,
)
from motor.core.fusion.stages.extraction import ExtractionStage
from motor.core.fusion.stages.merger import (
    KnowledgeMergerStage,
    SimpleKnowledgeMerger,
)
from motor.core.fusion.stages.normalization import NormalizationStage
from motor.core.fusion.stages.selector import (
    MemoryCandidateSelectionStage,
    ThresholdSelector,
)
from motor.core.fusion.stages.source_scorer import (
    QualitySourceScorer,
    SourceScoringStage,
)

__all__ = [
    "BasicChangeDetector",
    "CachePolicy",
    "ConflictDetectionStage",
    "ContextualEntityResolver",
    "EntityDef",
    "EntityRegistry",
    "EntityResolutionStage",
    "ExtractionStage",
    "KeywordScorer",
    "KnowledgeDeltaStage",
    "KnowledgeMergerStage",
    "LRUCache",
    "MemoryCandidateSelectionStage",
    "NaiveConflictResolver",
    "NormalizationStage",
    "QualitySourceScorer",
    "RuleBasedEntityResolver",
    "ScoringStrategy",
    "SimpleKnowledgeMerger",
    "SourceScoringStage",
    "ThresholdSelector",
]
