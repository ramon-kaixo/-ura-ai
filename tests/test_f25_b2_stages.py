"""Tests para F25-B2: Implementación PipelineStage."""

from __future__ import annotations

from motor.core.fusion.base import BaseStage, PipelineStage
from motor.core.fusion.config import FusionConfig, make_config_hash
from motor.core.fusion.engine import FusionStage
from motor.core.fusion.models import (
    EvidenceSet,
    FusionContext,
    FusionProvenance,
    FusionResult,
    KnowledgeClaim,
    KnowledgeFact,
    SourceScore,
    StageProvenance,
    make_claim_id,
)
from motor.core.fusion.stages import (
    BasicChangeDetector,
    ConflictDetectionStage,
    EntityResolutionStage,
    ExtractionStage,
    KnowledgeDeltaStage,
    KnowledgeMergerStage,
    MemoryCandidateSelectionStage,
    NaiveConflictResolver,
    NormalizationStage,
    QualitySourceScorer,
    RuleBasedEntityResolver,
    SimpleKnowledgeMerger,
    SourceScoringStage,
    ThresholdSelector,
)
from motor.core.web.citation.citation import CitationBundle, Evidence


# ── B2.1: Deterministic pipeline stage flag ────────────────

class _NonDeterministicStage(BaseStage):
    @property
    def stage(self) -> FusionStage: return FusionStage.EXTRACTION
    @property
    def name(self) -> str: return "NonDetStage"
    @property
    def version(self) -> str: return "1.0.0"
    @property
    def deterministic(self) -> bool: return False
    def _execute(self, context: FusionContext) -> FusionContext: return context


def test_pipeline_stage_deterministic_default() -> None:
    assert ExtractionStage().deterministic is True


def test_pipeline_stage_deterministic_override() -> None:
    assert _NonDeterministicStage().deterministic is False


# ── B2.2: config_hash ─────────────────────────────────────

def test_make_config_hash_deterministic() -> None:
    cfg = FusionConfig()
    h1 = make_config_hash(cfg)
    h2 = make_config_hash(cfg)
    assert h1 == h2, "config_hash must be deterministic"


def test_make_config_hash_length() -> None:
    cfg = FusionConfig()
    h = make_config_hash(cfg)
    assert len(h) == 16, f"Expected 16 hex chars, got {len(h)}"


def test_make_config_hash_changes_on_change() -> None:
    a = FusionConfig(max_claims_per_document=10)
    b = FusionConfig(max_claims_per_document=20)
    assert make_config_hash(a) != make_config_hash(b)


# ── B2.3: BaseStage automatic provenance ──────────────────

def _make_context() -> FusionContext:
    return FusionContext(
        bundle=CitationBundle(
            summary="test summary",
            citations=[],
            evidence=[
                Evidence(
                    evidence_id="ev1", document_url="https://example.com",
                    canonical_url=None, title="Test", document_index=0,
                    sentence_position=0, fragment="hello world",
                    content_hash="abc", document_id="doc1",
                    fetched_at=1000.0, quality_score=0.8,
                ),
            ],
        ),
        provenance=FusionProvenance(pipeline_version="1.0.0"),
    )


def test_extraction_stage_provenance() -> None:
    stage = ExtractionStage()
    ctx = _make_context()
    result = stage.execute(ctx)
    assert len(result.transforms) == 1
    t = result.transforms[0]
    assert t.stage_name == "ExtractionStage"
    assert t.transformer == "ExtractionStage:v1.0.0"
    assert t.input_claims == 0
    assert t.output_claims == 1


def test_extraction_stage_creates_claims() -> None:
    stage = ExtractionStage()
    ctx = _make_context()
    result = stage.execute(ctx)
    assert len(result.claims) == 1
    claim = result.claims[0]
    assert claim.text == "hello world"
    assert claim.confidence == 0.8
    assert claim.evidence is not None
    assert claim.evidence.evidence_id == "ev1"
    assert result.statistics["claims_extracted"] == 1


# ── B2.4: NormalizationStage ──────────────────────────────

def test_normalization_stage() -> None:
    ctx = FusionContext(
        claims=[
            KnowledgeClaim(
                id=make_claim_id("ev1", "  Hello   World!! "),
                text="  Hello   World!! ",
                confidence=0.8,
            ),
        ],
    )
    stage = NormalizationStage()
    result = stage.execute(ctx)
    assert result.claims[0].normalized_text == "hello world"


# ── B2.5: EntityResolutionStage ───────────────────────────

def test_rule_based_entity_resolver_known() -> None:
    resolver = RuleBasedEntityResolver()
    entity = resolver.resolve("apple")
    assert entity.status.value == "resolved"
    assert entity.canonical_name == "Apple"
    assert entity.entity_id != ""


def test_rule_based_entity_resolver_unknown() -> None:
    resolver = RuleBasedEntityResolver()
    entity = resolver.resolve("nonexistent_corp_12345")
    assert entity.status.value == "unknown"
    assert entity.entity_id == ""


def test_entity_resolution_stage() -> None:
    ctx = FusionContext(
        claims=[
            KnowledgeClaim(
                id=make_claim_id("ev1", "Apple is a company"),
                text="Apple is a company",
                confidence=0.8,
                normalized_text="apple is a company",
            ),
        ],
    )
    stage = EntityResolutionStage()
    result = stage.execute(ctx)
    assert result.statistics["entities_resolved"] >= 1


# ── B2.6: ConflictDetectionStage ──────────────────────────

def test_naive_conflict_resolver_detects() -> None:
    resolver = NaiveConflictResolver()
    claims = [
        KnowledgeClaim(
            id=make_claim_id("a", "Apple sells oranges"),
            text="Apple sells oranges",
            confidence=0.9,
            subject="apple",
            predicate="sells",
            object="oranges",
        ),
        KnowledgeClaim(
            id=make_claim_id("b", "Apple sells bananas"),
            text="Apple sells bananas",
            confidence=0.7,
            subject="apple",
            predicate="sells",
            object="bananas",
        ),
    ]
    conflicts = resolver.detect(claims)
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type.value == "contradiction"


def test_naive_conflict_resolver_no_conflict() -> None:
    resolver = NaiveConflictResolver()
    claims = [
        KnowledgeClaim(
            id=make_claim_id("a", "Apple sells oranges"),
            text="Apple sells oranges",
            confidence=0.9,
            subject="apple",
            predicate="sells",
            object="oranges",
        ),
        KnowledgeClaim(
            id=make_claim_id("b", "Google sells ads"),
            text="Google sells ads",
            confidence=0.9,
            subject="google",
            predicate="sells",
            object="ads",
        ),
    ]
    assert len(resolver.detect(claims)) == 0


def test_conflict_detection_stage() -> None:
    ctx = FusionContext(
        claims=[
            KnowledgeClaim(
                id=make_claim_id("a", "Apple sells oranges"),
                text="Apple sells oranges",
                confidence=0.9,
                subject="apple",
                predicate="sells",
                object="oranges",
            ),
            KnowledgeClaim(
                id=make_claim_id("b", "Apple sells bananas"),
                text="Apple sells bananas",
                confidence=0.7,
                subject="apple",
                predicate="sells",
                object="bananas",
            ),
        ],
    )
    stage = ConflictDetectionStage()
    result = stage.execute(ctx)
    assert result.statistics["conflicts_detected"] == 1


# ── B2.7: SourceScoringStage ──────────────────────────────

def test_quality_source_scorer() -> None:
    scorer = QualitySourceScorer()
    claim = KnowledgeClaim(
        id=make_claim_id("ev1", "test"),
        text="test",
        confidence=0.5,
        evidence=Evidence(
            evidence_id="ev1", document_url="https://example.gov/doc",
            canonical_url=None, title="", document_index=0,
            sentence_position=0, fragment="test",
            content_hash="abc", document_id="d",
            fetched_at=1000000.0, quality_score=0.8,
        ),
    )
    score = scorer.score(claim)
    assert score.authority > 0.5  # .gov TLD
    assert score.overall > 0


def test_source_scoring_stage() -> None:
    claim = KnowledgeClaim(
        id=make_claim_id("ev1", "test"),
        text="test",
        confidence=0.5,
        evidence=Evidence(
            evidence_id="ev1", document_url="https://example.gov/doc",
            canonical_url=None, title="", document_index=0,
            sentence_position=0, fragment="test",
            content_hash="abc", document_id="d",
            fetched_at=1000000.0, quality_score=0.8,
        ),
    )
    ctx = FusionContext(claims=[claim])
    stage = SourceScoringStage()
    result = stage.execute(ctx)
    assert result.claims[0].source_score is not None


# ── B2.8: KnowledgeMergerStage ────────────────────────────

def test_simple_knowledge_merger() -> None:
    claim = KnowledgeClaim(
        id=make_claim_id("ev1", "Apple sells oranges"),
        text="Apple sells oranges",
        confidence=0.9,
    )
    merger = SimpleKnowledgeMerger()
    facts = merger.merge([claim], [])
    assert len(facts) == 1
    assert facts[0].subject == "Apple"
    assert facts[0].predicate == "sells"
    assert facts[0].object == "oranges"


def test_knowledge_merger_stage() -> None:
    claim = KnowledgeClaim(
        id=make_claim_id("ev1", "Apple sells oranges"),
        text="Apple sells oranges",
        confidence=0.9,
    )
    ctx = FusionContext(claims=[claim])
    stage = KnowledgeMergerStage()
    result = stage.execute(ctx)
    assert len(result.facts) == 1
    assert result.facts[0].id != ""


# ── B2.9: KnowledgeDeltaStage ─────────────────────────────

def test_basic_change_detector_added() -> None:
    from motor.core.fusion.models import KnowledgeFact
    fact = KnowledgeFact(
        id="fact1", subject="Apple", predicate="sells", object="oranges", confidence=0.9,
    )
    detector = BasicChangeDetector()
    delta = detector.detect_delta([fact], [])
    assert len(delta.facts_added) == 1
    assert delta.has_changes


def test_basic_change_detector_confirmed() -> None:
    from motor.core.fusion.models import KnowledgeFact
    fact = KnowledgeFact(
        id="fact1", subject="Apple", predicate="sells", object="oranges", confidence=0.9,
    )
    detector = BasicChangeDetector()
    delta = detector.detect_delta([fact], [fact])
    assert len(delta.facts_added) == 0
    assert len(delta.facts_updated) == 0


def test_knowledge_delta_stage() -> None:
    from motor.core.fusion.models import KnowledgeFact
    fact = KnowledgeFact(
        id="fact1", subject="Apple", predicate="sells", object="oranges", confidence=0.9,
    )
    ctx = FusionContext(facts=[fact], statistics={"existing_facts": []})
    stage = KnowledgeDeltaStage()
    result = stage.execute(ctx)
    assert result.statistics["deltas_added"] == 1
    assert result.statistics["has_changes"] is True


# ── B2.10: MemoryCandidateSelectionStage ──────────────────

def test_threshold_selector() -> None:
    from motor.core.fusion.models import FusionResult, KnowledgeFact
    facts = [
        KnowledgeFact(id="a", subject="S", predicate="P", object="O1", confidence=0.1),
        KnowledgeFact(id="b", subject="S", predicate="P", object="O2", confidence=0.5),
        KnowledgeFact(id="c", subject="S", predicate="P", object="O3", confidence=0.9),
    ]
    result = FusionResult(accepted=tuple(facts))
    selector = ThresholdSelector(min_confidence=0.3)
    selected = selector.select(result, max_candidates=10)
    assert len(selected) == 2  # 0.5 and 0.9
    assert selected[0].id == "c"  # highest confidence first


def test_memory_candidate_selection_stage() -> None:
    ctx = FusionContext()
    stage = MemoryCandidateSelectionStage()
    result = stage.execute(ctx)
    assert result.statistics["candidates_requested"] == 100


# ── B2.11: config_hash integration ────────────────────────

def test_config_hash_in_provenance() -> None:
    cfg = FusionConfig()
    ctx = FusionContext(
        provenance=FusionProvenance(
            pipeline_version="1.0.0",
            config_hash=make_config_hash(cfg),
        ),
    )
    assert len(ctx.provenance.config_hash) == 16
    assert ctx.provenance.config_hash == make_config_hash(cfg)


def test_stage_provenance_has_timestamp() -> None:
    t = StageProvenance(
        stage_name="Test",
        stage_version="1.0.0",
        transformer="Test:v1.0.0",
        input_claims=5,
        output_claims=3,
    )
    assert t.timestamp > 0


# ── D01: Bucket-based conflict detection ──────────────────

def test_conflict_detection_buckets_different_subjects() -> None:
    """Claims with different subjects are not compared (no O(n²) across subjects)."""
    claims = [
        KnowledgeClaim(
            id=make_claim_id(f"ev{i}", f"Entity{i} sells stuff"),
            text=f"Entity{i} sells stuff", confidence=0.9,
            subject=f"entity{i}", predicate="sells", object="stuff",
        )
        for i in range(100)
    ]
    resolver = NaiveConflictResolver()
    conflicts = resolver.detect(claims)
    assert len(conflicts) == 0


def test_conflict_detection_buckets_same_subject() -> None:
    """Claims sharing (subject, predicate) are compared."""
    claims = [
        KnowledgeClaim(
            id=make_claim_id("a", "Apple sells oranges"),
            text="Apple sells oranges", confidence=0.9,
            subject="apple", predicate="sells", object="oranges",
        ),
        KnowledgeClaim(
            id=make_claim_id("b", "Apple sells bananas"),
            text="Apple sells bananas", confidence=0.7,
            subject="apple", predicate="sells", object="bananas",
        ),
        KnowledgeClaim(
            id=make_claim_id("c", "Apple sells bananas"),
            text="Apple sells bananas", confidence=0.8,
            subject="apple", predicate="sells", object="bananas",
        ),
    ]
    resolver = NaiveConflictResolver()
    conflicts = resolver.detect(claims)
    assert len(conflicts) == 2  # (a,b) and (a,c) — b and c have same object


# ── D02: text_id + evidence_ids ──────────────────────────

def test_text_id_in_claim() -> None:
    from motor.core.web.citation.citation import Evidence
    ev = Evidence(
        evidence_id="ev1", document_url="https://example.com",
        canonical_url=None, title="T", document_index=0,
        sentence_position=0, fragment="hello",
        content_hash="abc", document_id="d",
        fetched_at=1000.0, quality_score=0.8,
    )
    claim = KnowledgeClaim(
        id=make_claim_id("ev1", "hello"),
        text="hello", confidence=0.8,
        evidence=ev,
        text_id=ev.evidence_id,
    )
    assert claim.text_id == "ev1"


def test_evidence_ids_in_fact() -> None:
    from motor.core.fusion.models import make_fact_id
    fid = make_fact_id("Apple", "sells", "oranges")
    fact = KnowledgeFact(
        id=fid, subject="Apple", predicate="sells",
        object="oranges", confidence=0.9,
        evidence_ids=("ev1", "ev2"),
    )
    assert fact.evidence_ids == ("ev1", "ev2")
    assert len(fact.evidence) == 0  # no full Evidence objects


def test_extraction_stage_sets_text_id() -> None:
    ctx = _make_context()
    stage = ExtractionStage()
    result = stage.execute(ctx)
    assert result.claims[0].text_id == "ev1"


def test_merger_uses_evidence_ids() -> None:
    claim = KnowledgeClaim(
        id=make_claim_id("ev1", "Apple sells oranges"),
        text="Apple sells oranges", confidence=0.9,
        text_id="ev1",
    )
    merger = SimpleKnowledgeMerger()
    facts = merger.merge([claim], [])
    assert len(facts) == 1
    assert facts[0].evidence_ids == ("ev1",)
    assert len(facts[0].evidence) == 0  # no full objects
    assert facts[0].id != ""  # pre-computed, no object.__setattr__


# ── D03: Complete FusionProvenance ────────────────────────

def test_provenance_all_fields_set() -> None:
    """Every stage populates its slice of FusionProvenance."""
    from motor.core.fusion.stages import (
        ConflictDetectionStage, EntityResolutionStage,
        KnowledgeDeltaStage, KnowledgeMergerStage,
        MemoryCandidateSelectionStage, SourceScoringStage,
    )

    ctx = FusionContext(
        claims=[
            KnowledgeClaim(
                id=make_claim_id("ev1", "Apple sells oranges"),
                text="Apple sells oranges", confidence=0.9,
                subject="apple", predicate="sells", object="oranges",
                text_id="ev1",
            ),
        ],
    )

    # EntityResolution (now defaults to ContextualEntityResolver)
    ctx = EntityResolutionStage().execute(ctx)
    assert ctx.provenance.resolver_name == "ContextualEntityResolver"
    assert ctx.provenance.resolver_version == "3.0.0"

    # ConflictDetection
    ctx = ConflictDetectionStage().execute(ctx)
    assert ctx.provenance.conflict_resolver_name == "NaiveConflictResolver"
    assert ctx.provenance.conflict_resolver_version == "1.0.0"

    # SourceScoring
    ctx = SourceScoringStage().execute(ctx)
    assert ctx.provenance.source_scorer_name == "QualitySourceScorer"
    assert ctx.provenance.source_scorer_version == "1.0.0"

    # KnowledgeMerger
    ctx = KnowledgeMergerStage().execute(ctx)
    assert ctx.provenance.merger_name == "SimpleKnowledgeMerger"
    assert ctx.provenance.merger_version == "1.0.0"

    # KnowledgeDelta
    ctx = KnowledgeDeltaStage().execute(ctx)
    assert ctx.provenance.change_detector_name == "BasicChangeDetector"
    assert ctx.provenance.change_detector_version == "1.0.0"

    # MemoryCandidateSelection
    ctx = MemoryCandidateSelectionStage().execute(ctx)
    assert ctx.provenance.selector_name == "ThresholdSelector"
    assert ctx.provenance.selector_version == "1.0.0"
