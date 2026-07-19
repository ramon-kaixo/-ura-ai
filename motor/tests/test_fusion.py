"""Tests de contratos F25-B1 — Knowledge Fusion Architecture.

Verifica modelos, ABCs, registry, pipeline etapas, IDs deterministas,
inmutabilidad de Facts, y estructura de FusionResult.
"""

from __future__ import annotations

from motor.core.fusion import (
    ChangeDetector,
    Conflict,
    ConflictResolver,
    ConflictType,
    EntityResolver,
    EvidenceSet,
    FusionConfig,
    FusionContext,
    FusionEngine,
    FusionPipeline,
    FusionProvenance,
    FusionRegistry,
    FusionResult,
    FusionStage,
    KnowledgeClaim,
    KnowledgeDelta,
    KnowledgeFact,
    KnowledgeMerger,
    MemoryCandidateSelector,
    PipelineStage,
    ResolutionStatus,
    ResolvedEntity,
    SourceScore,
    SourceScorer,
    StageProvenance,
    make_claim_id,
    make_conflict_id,
    make_fact_id,
)
from motor.core.web.citation.citation import Evidence

# ── Stubs compartidos para tests de contratos ──


class _StubEngine(FusionEngine):
    def fuse(self, bundle, documents):
        return FusionResult(accepted=())


class _StubResolver(ConflictResolver):
    def detect(self, claims):
        return []

    def resolve(self, conflicts, claims):
        return [], []


class _StubScorer(SourceScorer):
    def score(self, claim):
        return SourceScore(url="http://test.com")

    def score_evidence(self, evidence_set):
        return []


class _StubMerger(KnowledgeMerger):
    def merge(self, claims, conflicts):
        return []


class _StubDetector(ChangeDetector):
    def detect_delta(self, new_facts, existing_facts):
        return KnowledgeDelta()


class _StubSelector(MemoryCandidateSelector):
    def select(self, fusion_result, max_candidates=100):
        return []


class _StubEntityResolver(EntityResolver):
    @property
    def version(self) -> str:
        return "1.0.0"

    def resolve(self, text, context=None):
        return ResolvedEntity(
            entity_id="E000123",
            canonical_name="Apple",
            confidence=0.95,
            aliases=("Apple Inc.", "Apple Computer"),
            resolver_name="stub",
            resolver_version=self.version,
        )

    def resolve_many(self, texts, context=None):
        return [self.resolve(t) for t in texts]

    def normalize(self, text):
        return text.strip().lower()


# ── IDs deterministas ──────────────────────


class TestMakeClaimId:
    def test_deterministic(self) -> None:
        a = make_claim_id("ev1", "Company X was founded in 2018")
        b = make_claim_id("ev1", "Company X was founded in 2018")
        assert a == b
        assert len(a) == 16

    def test_different_text(self) -> None:
        a = make_claim_id("ev1", "Company X was founded in 2018")
        b = make_claim_id("ev1", "Company X was founded in 2019")
        assert a != b

    def test_different_evidence(self) -> None:
        a = make_claim_id("ev1", "Same text")
        b = make_claim_id("ev2", "Same text")
        assert a != b

    def test_case_insensitive(self) -> None:
        a = make_claim_id("ev1", "Hello World")
        b = make_claim_id("ev1", "hello world")
        assert a == b

    def test_strips_whitespace(self) -> None:
        a = make_claim_id("ev1", "  text  ")
        b = make_claim_id("ev1", "text")
        assert a == b


class TestMakeFactId:
    def test_deterministic(self) -> None:
        a = make_fact_id("Apple", "CEO", "Tim Cook")
        b = make_fact_id("Apple", "CEO", "Tim Cook")
        assert a == b
        assert len(a) == 16

    def test_different_subject(self) -> None:
        assert make_fact_id("Apple", "CEO", "Tim") != make_fact_id("Microsoft", "CEO", "Tim")

    def test_different_predicate(self) -> None:
        assert make_fact_id("Apple", "CEO", "Tim") != make_fact_id("Apple", "founder", "Tim")

    def test_different_version(self) -> None:
        assert make_fact_id("Apple", "CEO", "Tim", version=1) != make_fact_id("Apple", "CEO", "Tim", version=2)

    def test_default_version_is_1(self) -> None:
        a = make_fact_id("X", "Y", "Z")
        b = make_fact_id("X", "Y", "Z", version=1)
        assert a == b


class TestMakeConflictId:
    def test_deterministic(self) -> None:
        a = make_conflict_id("c1", "c2", "contradiction")
        b = make_conflict_id("c1", "c2", "contradiction")
        assert a == b
        assert len(a) == 16

    def test_different_type(self) -> None:
        ct = make_conflict_id("c1", "c2", "contradiction")
        tu = make_conflict_id("c1", "c2", "temporal_update")
        assert ct != tu

    def test_swap_order(self) -> None:
        a = make_conflict_id("c1", "c2", "contradiction")
        b = make_conflict_id("c2", "c1", "contradiction")
        assert a != b


# ── SourceScore ────────────────────────────


class TestSourceScore:
    def test_defaults(self) -> None:
        s = SourceScore(url="http://example.com")
        assert s.url == "http://example.com"
        assert s.authority == 0.0
        assert s.freshness == 0.0
        assert s.corroboration == 0.0
        assert s.internal_consistency == 0.0
        assert s.historical_accuracy == 0.0
        assert s.citation_quality == 0.0
        assert s.overall == 0.0

    def test_full_construction(self) -> None:
        s = SourceScore(
            url="http://a.com",
            authority=0.9,
            freshness=0.8,
            corroboration=0.7,
            internal_consistency=0.85,
            historical_accuracy=0.75,
            citation_quality=0.95,
            overall=0.82,
        )
        assert s.authority == 0.9
        assert s.corroboration == 0.7
        assert s.internal_consistency == 0.85
        assert s.historical_accuracy == 0.75
        assert s.citation_quality == 0.95
        assert s.overall == 0.82

    def test_is_mutable(self) -> None:
        s = SourceScore(url="http://a.com")
        s.authority = 0.5
        assert s.authority == 0.5


# ── ResolvedEntity ─────────────────────────


class TestResolvedEntity:
    def test_create_minimal(self) -> None:
        e = ResolvedEntity(
            entity_id="E000123",
            canonical_name="Apple",
            confidence=0.95,
        )
        assert e.entity_id == "E000123"
        assert e.canonical_name == "Apple"
        assert e.confidence == 0.95
        assert e.status == ResolutionStatus.RESOLVED
        assert e.aliases == ()
        assert e.resolver_name == ""
        assert e.resolver_version == ""

    def test_create_full(self) -> None:
        e = ResolvedEntity(
            entity_id="",
            canonical_name="Unresolved",
            confidence=0.0,
            status=ResolutionStatus.UNKNOWN,
            aliases=(),
            resolver_name="generic",
            resolver_version="1.0.0",
        )
        assert e.status == ResolutionStatus.UNKNOWN
        assert e.resolver_name == "generic"

    def test_abstention_explicit_status(self) -> None:
        """Abstención: status=UNKNOWN en lugar de forzar resolución."""
        e = ResolvedEntity(
            entity_id="",
            canonical_name="Unresolved",
            confidence=0.0,
            status=ResolutionStatus.UNKNOWN,
        )
        assert e.status == ResolutionStatus.UNKNOWN
        assert e.confidence == 0.0


# ── ResolutionStatus ──────────────────────


class TestResolutionStatus:
    def test_values(self) -> None:
        assert ResolutionStatus.RESOLVED.value == "resolved"
        assert ResolutionStatus.UNKNOWN.value == "unknown"
        assert ResolutionStatus.AMBIGUOUS.value == "ambiguous"
        assert ResolutionStatus.ERROR.value == "error"

    def test_all_unique(self) -> None:
        values = [s.value for s in ResolutionStatus]
        assert len(values) == len(set(values))


# ── FusionProvenance ──────────────────────


class TestFusionProvenance:
    def test_defaults(self) -> None:
        p = FusionProvenance()
        assert p.pipeline_version == ""
        assert p.resolver_name == ""
        assert p.resolver_version == ""
        assert p.conflict_resolver_name == ""
        assert p.conflict_resolver_version == ""
        assert p.merger_name == ""
        assert p.merger_version == ""
        assert p.source_scorer_name == ""
        assert p.source_scorer_version == ""
        assert p.config_hash == ""

    def test_full(self) -> None:
        p = FusionProvenance(
            pipeline_version="1.0.0",
            resolver_name="generic",
            resolver_version="2.1.0",
            merger_name="weighted",
            merger_version="1.0.0",
            config_hash="abc123",
        )
        assert p.pipeline_version == "1.0.0"
        assert p.resolver_version == "2.1.0"


# ── StageProvenance ──────────────────────


class TestStageProvenance:
    def test_create(self) -> None:
        sp = StageProvenance(
            stage_name="EntityResolutionStage",
            stage_version="1.0.0",
            transformer="EntityResolver:generic:v2.1",
            input_claims=10,
            output_claims=8,
        )
        assert sp.stage_name == "EntityResolutionStage"
        assert sp.transformer == "EntityResolver:generic:v2.1"
        assert sp.input_claims == 10


# ── FusionContext ─────────────────────────


class TestFusionContext:
    def test_defaults(self) -> None:
        ctx = FusionContext()
        assert ctx.claims == []
        assert ctx.entities == []
        assert ctx.conflicts == []
        assert ctx.facts == []
        assert ctx.warnings == []
        assert ctx.statistics == {}
        assert isinstance(ctx.provenance, FusionProvenance)
        assert ctx.transforms == []

    def test_accumulates_transforms(self) -> None:
        ctx = FusionContext()
        ctx.transforms.append(
            StageProvenance(
                stage_name="ExtractionStage",
                stage_version="1.0",
                transformer="test",
            ),
        )
        assert len(ctx.transforms) == 1


# ── KnowledgeClaim (mutable) ───────────────


class TestKnowledgeClaim:
    def test_create_minimal(self) -> None:
        c = KnowledgeClaim(
            id=make_claim_id("ev1", "Apple CEO is Tim Cook"),
            text="Apple CEO is Tim Cook",
            confidence=0.8,
        )
        assert len(c.id) == 16
        assert c.text == "Apple CEO is Tim Cook"
        assert c.confidence == 0.8
        assert c.evidence is None
        assert c.normalized_text == ""
        assert c.subject == ""
        assert c.predicate == ""
        assert c.object == ""

    def test_create_with_evidence(self) -> None:
        ev = Evidence(
            evidence_id="ev1",
            document_url="http://example.com",
            canonical_url=None,
            title="Test",
            document_index=0,
            sentence_position=1,
            fragment="Apple CEO is Tim Cook",
            content_hash="abc",
            document_id="doc1",
            fetched_at=1000.0,
            quality_score=0.9,
        )
        c = KnowledgeClaim(
            id=make_claim_id("ev1", "Apple CEO is Tim Cook"),
            text="Apple CEO is Tim Cook",
            confidence=0.8,
            evidence=ev,
        )
        assert c.evidence is not None
        assert c.evidence.evidence_id == "ev1"

    def test_is_mutable(self) -> None:
        c = KnowledgeClaim(id="c1", text="T", confidence=0.5)
        c.normalized_text = "normalized"
        c.subject = "Apple"
        c.predicate = "CEO"
        c.object = "Tim Cook"
        c.confidence = 0.9
        assert c.subject == "Apple"
        assert c.normalized_text == "normalized"

    def test_enrichment_during_pipeline(self) -> None:
        """Claim empieza con texto crudo, se enriquece con normalización."""
        c = KnowledgeClaim(
            id=make_claim_id("ev1", "Apple CEO is Tim Cook"),
            text="Apple CEO is Tim Cook",
            confidence=0.8,
        )
        c.subject = "Apple"
        c.predicate = "CEO"
        c.object = "Tim Cook"
        c.source_score = SourceScore(url="http://a.com", overall=0.9)
        assert c.subject == "Apple"
        assert c.source_score.overall == 0.9


# ── ConflictType ───────────────────────────


class TestConflictType:
    def test_values(self) -> None:
        assert ConflictType.CONTRADICTION.value == "contradiction"
        assert ConflictType.TEMPORAL_UPDATE.value == "temporal_update"
        assert ConflictType.DIFFERENT_GRANULARITY.value == "different_granularity"
        assert ConflictType.DIFFERENT_SCOPE.value == "different_scope"
        assert ConflictType.OPINION.value == "opinion"

    def test_all_unique(self) -> None:
        values = [t.value for t in ConflictType]
        assert len(values) == len(set(values))


# ── Conflict (mutable, se resuelve) ────────


class TestConflict:
    def test_create_minimal(self) -> None:
        cid = make_conflict_id("c1", "c2", "contradiction")
        con = Conflict(id=cid, claim_a="c1", claim_b="c2")
        assert len(con.id) == 16
        assert con.claim_a == "c1"
        assert con.claim_b == "c2"
        assert con.conflict_type == ConflictType.CONTRADICTION
        assert con.resolved is False
        assert con.resolution is None

    def test_create_with_type(self) -> None:
        cid = make_conflict_id("c1", "c2", "temporal_update")
        con = Conflict(
            id=cid,
            claim_a="c1",
            claim_b="c2",
            conflict_type=ConflictType.TEMPORAL_UPDATE,
            description="Different years",
        )
        assert con.conflict_type == ConflictType.TEMPORAL_UPDATE
        assert con.description == "Different years"

    def test_resolution_mutable(self) -> None:
        cid = make_conflict_id("c1", "c2", "contradiction")
        con = Conflict(id=cid, claim_a="c1", claim_b="c2")
        con.resolved = True
        con.resolution = "Using most recent source"
        assert con.resolved is True
        assert "recent" in con.resolution


# ── KnowledgeFact (inmutable) ──────────────


class TestKnowledgeFact:
    def test_create_minimal(self) -> None:
        fid = make_fact_id("Apple", "CEO", "Tim Cook")
        f = KnowledgeFact(
            id=fid,
            subject="Apple",
            predicate="CEO",
            object="Tim Cook",
            confidence=0.85,
        )
        assert len(f.id) == 16
        assert f.subject == "Apple"
        assert f.predicate == "CEO"
        assert f.object == "Tim Cook"
        assert f.confidence == 0.85
        assert f.evidence == ()
        assert f.provenance == ()
        assert f.version == 1
        assert f.superseded_by is None

    def test_is_frozen(self) -> None:
        fid = make_fact_id("Apple", "CEO", "Tim Cook")
        f = KnowledgeFact(id=fid, subject="Apple", predicate="CEO", object="Tim Cook", confidence=0.8)
        try:
            f.confidence = 0.9
            msg = "Should have raised FrozenInstanceError"
            raise AssertionError(msg)
        except Exception as e:
            assert type(e).__name__ in ("FrozenInstanceError", "AttributeError")

    def test_versioning(self) -> None:
        fid_v1 = make_fact_id("Apple", "CEO", "Tim Cook", version=1)
        fid_v2 = make_fact_id("Apple", "CEO", "Tim Cook", version=2)
        f1 = KnowledgeFact(id=fid_v1, subject="Apple", predicate="CEO", object="Tim Cook", confidence=0.8)
        f2 = KnowledgeFact(
            id=fid_v2,
            subject="Apple",
            predicate="CEO",
            object="Tim Cook",
            confidence=0.95,
            version=2,
            superseded_by=None,
        )
        assert f1.version == 1
        assert f2.version == 2
        assert f1.id != f2.id

    def test_superseded_by(self) -> None:
        fid_v1 = make_fact_id("Apple", "CEO", "Tim Cook", version=1)
        fid_v2 = make_fact_id("Apple", "CEO", "Tim Cook", version=2)
        f1 = KnowledgeFact(
            id=fid_v1,
            subject="Apple",
            predicate="CEO",
            object="Tim Cook",
            confidence=0.8,
            version=1,
            superseded_by=fid_v2,
        )
        assert f1.superseded_by == fid_v2

    def test_provenance_preserved(self) -> None:
        fid = make_fact_id("Apple", "CEO", "Tim Cook")
        f = KnowledgeFact(
            id=fid,
            subject="Apple",
            predicate="CEO",
            object="Tim Cook",
            confidence=0.85,
            provenance=("c1", "c2"),
        )
        assert f.provenance == ("c1", "c2")

    def test_evidence_is_tuple(self) -> None:
        ev = Evidence(
            evidence_id="ev1",
            document_url="http://example.com",
            canonical_url=None,
            title="Test",
            document_index=0,
            sentence_position=1,
            fragment="Apple CEO is Tim Cook",
            content_hash="abc",
            document_id="doc1",
            fetched_at=1000.0,
            quality_score=0.9,
        )
        fid = make_fact_id("Apple", "CEO", "Tim Cook")
        f = KnowledgeFact(
            id=fid,
            subject="Apple",
            predicate="CEO",
            object="Tim Cook",
            confidence=0.85,
            evidence=(ev,),
        )
        assert isinstance(f.evidence, tuple)
        assert len(f.evidence) == 1
        assert f.evidence[0].evidence_id == "ev1"


# ── EvidenceSet ────────────────────────────


class TestEvidenceSet:
    def test_empty(self) -> None:
        es = EvidenceSet()
        assert len(es) == 0
        assert es.claims == []
        assert es.source_documents == []

    def test_with_claims(self) -> None:
        c1 = KnowledgeClaim(id="c1", text="C1", confidence=0.8)
        c2 = KnowledgeClaim(id="c2", text="C2", confidence=0.9)
        es = EvidenceSet(claims=[c1, c2], source_documents=["http://a.com"])
        assert len(es) == 2
        assert es.claims[0].id == "c1"

    def test_len(self) -> None:
        es = EvidenceSet()
        assert len(es) == 0
        es.claims.append(KnowledgeClaim(id="c1", text="T", confidence=0.5))
        assert len(es) == 1


# ── FusionResult (estadísticas + trazabilidad) ──


class TestFusionResult:
    def test_empty(self) -> None:
        r = FusionResult()
        assert r.accepted == ()
        assert r.rejected == ()
        assert r.conflicts == ()
        assert r.warnings == ()
        assert r.statistics == {}
        assert isinstance(r.provenance, FusionProvenance)

    def test_accepted_facts(self) -> None:
        f = KnowledgeFact(
            id=make_fact_id("Apple", "CEO", "Tim Cook"),
            subject="Apple",
            predicate="CEO",
            object="Tim Cook",
            confidence=0.9,
        )
        r = FusionResult(accepted=(f,))
        assert len(r.accepted) == 1
        assert r.accepted[0].subject == "Apple"

    def test_rejected_claims(self) -> None:
        c = KnowledgeClaim(id="c1", text="Rejected", confidence=0.1)
        r = FusionResult(rejected=(c,))
        assert len(r.rejected) == 1
        assert r.rejected[0].text == "Rejected"

    def test_conflicts(self) -> None:
        cid = make_conflict_id("c1", "c2", "contradiction")
        con = Conflict(id=cid, claim_a="c1", claim_b="c2")
        r = FusionResult(conflicts=(con,))
        assert len(r.conflicts) == 1
        assert r.conflicts[0].claim_a == "c1"

    def test_warnings(self) -> None:
        r = FusionResult(warnings=("Low confidence claim skipped",))
        assert len(r.warnings) == 1
        assert "Low confidence" in r.warnings[0]

    def test_statistics(self) -> None:
        r = FusionResult(statistics={"claims_input": 10, "facts_output": 3})
        assert r.statistics["claims_input"] == 10

    def test_all_tuples(self) -> None:
        """Verifica que todas las colecciones sean tuplas (inmutables)."""
        r = FusionResult()
        assert isinstance(r.accepted, tuple)
        assert isinstance(r.rejected, tuple)
        assert isinstance(r.conflicts, tuple)
        assert isinstance(r.warnings, tuple)


# ── KnowledgeDelta ──────────────────────────


class TestKnowledgeDelta:
    def test_empty(self) -> None:
        d = KnowledgeDelta()
        assert d.has_changes is False
        assert d.facts_added == ()
        assert d.facts_updated == ()
        assert d.facts_removed == ()
        assert d.conflicts_resolved == 0
        assert d.conflicts_new == 0

    def test_has_changes(self) -> None:
        f = KnowledgeFact(
            id=make_fact_id("A", "B", "C"),
            subject="A",
            predicate="B",
            object="C",
            confidence=0.5,
        )
        d = KnowledgeDelta(facts_added=(f,))
        assert d.has_changes is True

    def test_removed_is_tuple_of_tuples(self) -> None:
        d = KnowledgeDelta(facts_removed=(("f1",), ("f2",)))
        assert d.has_changes is True
        assert d.facts_removed == (("f1",), ("f2",))

    def test_all_tuples(self) -> None:
        d = KnowledgeDelta()
        assert isinstance(d.facts_added, tuple)
        assert isinstance(d.facts_updated, tuple)
        assert isinstance(d.facts_removed, tuple)


# ── ABCs (contract tests) ─────────────────


class TestFusionEngineContract:
    def test_is_abstract(self) -> None:
        try:
            FusionEngine()
            raise AssertionError
        except TypeError:
            pass

    def test_valid_subclass(self) -> None:
        class E(FusionEngine):
            def fuse(self, bundle, documents):
                return FusionResult()

        assert isinstance(E(), FusionEngine)


class TestConflictResolverContract:
    def test_is_abstract(self) -> None:
        try:
            ConflictResolver()
            raise AssertionError
        except TypeError:
            pass

    def test_valid_subclass(self) -> None:
        class R(ConflictResolver):
            def detect(self, claims):
                return []

            def resolve(self, conflicts, claims):
                return [], []

        assert isinstance(R(), ConflictResolver)


class TestSourceScorerContract:
    def test_is_abstract(self) -> None:
        try:
            SourceScorer()
            raise AssertionError
        except TypeError:
            pass

    def test_valid_subclass(self) -> None:
        class S(SourceScorer):
            def score(self, claim):
                return SourceScore(url="http://test.com")

            def score_evidence(self, evidence_set):
                return []

        assert isinstance(S(), SourceScorer)


class TestEntityResolverContract:
    def test_is_abstract(self) -> None:
        try:
            EntityResolver()
            raise AssertionError
        except TypeError:
            pass

    def test_valid_subclass(self) -> None:
        r = _StubEntityResolver()
        result = r.resolve("Apple Inc.")
        assert isinstance(result, ResolvedEntity)
        assert result.entity_id == "E000123"
        assert result.canonical_name == "Apple"
        assert result.confidence == 0.95
        assert "Apple Inc." in result.aliases
        assert result.resolver_version == "1.0.0"
        assert r.normalize("Apple Inc.") == "apple inc."
        results = r.resolve_many(["A", "B"])
        assert len(results) == 2
        assert all(isinstance(x, ResolvedEntity) for x in results)
        assert isinstance(r, EntityResolver)
        assert r.version == "1.0.0"


class TestKnowledgeMergerContract:
    def test_is_abstract(self) -> None:
        try:
            KnowledgeMerger()
            raise AssertionError
        except TypeError:
            pass

    def test_valid_subclass(self) -> None:
        class M(KnowledgeMerger):
            def merge(self, claims, conflicts):
                return []

        assert isinstance(M(), KnowledgeMerger)


class TestChangeDetectorContract:
    def test_is_abstract(self) -> None:
        try:
            ChangeDetector()
            raise AssertionError
        except TypeError:
            pass

    def test_valid_subclass(self) -> None:
        class D(ChangeDetector):
            def detect_delta(self, new_facts, existing_facts):
                return KnowledgeDelta()

        assert isinstance(D(), ChangeDetector)


class TestMemoryCandidateSelectorContract:
    def test_is_abstract(self) -> None:
        try:
            MemoryCandidateSelector()
            raise AssertionError
        except TypeError:
            pass

    def test_valid_subclass(self) -> None:
        class S(MemoryCandidateSelector):
            def select(self, fusion_result, max_candidates=100):
                return []

        assert isinstance(S(), MemoryCandidateSelector)


class TestPipelineStageContract:
    def test_is_abstract(self) -> None:
        try:
            PipelineStage()
            raise AssertionError
        except TypeError:
            pass

    def test_valid_subclass(self) -> None:
        stage = _make_stub_stage(FusionStage.EXTRACTION)
        assert stage.stage == FusionStage.EXTRACTION
        assert stage.name == "StubStage"
        assert stage.version == "0.0.0"
        ctx = FusionContext()
        result = stage.execute(ctx)
        assert isinstance(result, FusionContext)

    def test_multiple_stages_chain(self) -> None:
        class StageA(PipelineStage):
            @property
            def stage(self) -> FusionStage:
                return FusionStage.NORMALIZATION

            @property
            def name(self) -> str:
                return "StageA"

            @property
            def version(self) -> str:
                return "1.0"

            def execute(self, ctx: FusionContext) -> FusionContext:
                ctx.statistics["x"] = ctx.statistics.get("x", 0) + 1
                return ctx

        class StageB(PipelineStage):
            @property
            def stage(self) -> FusionStage:
                return FusionStage.MERGE

            @property
            def name(self) -> str:
                return "StageB"

            @property
            def version(self) -> str:
                return "2.0"

            def execute(self, ctx: FusionContext) -> FusionContext:
                ctx.statistics["x"] = ctx.statistics.get("x", 0) + 2
                return ctx

        ctx = FusionContext()
        ctx = StageA().execute(ctx)
        ctx = StageB().execute(ctx)
        assert ctx.statistics["x"] == 3

    def test_registers_transform(self) -> None:
        """Cada etapa debe registrar su transformación en context.transforms."""

        class TrackingStage(PipelineStage):
            @property
            def stage(self) -> FusionStage:
                return FusionStage.EXTRACTION

            @property
            def name(self) -> str:
                return "TrackingStage"

            @property
            def version(self) -> str:
                return "1.0"

            def execute(self, ctx: FusionContext) -> FusionContext:
                ctx.transforms.append(
                    StageProvenance(
                        stage_name=self.name,
                        stage_version=self.version,
                        transformer="TrackingStage:v1",
                        input_claims=0,
                        output_claims=0,
                    ),
                )
                return ctx

        ctx = TrackingStage().execute(FusionContext())
        assert len(ctx.transforms) == 1
        assert ctx.transforms[0].stage_name == "TrackingStage"


def _make_stub_stage(stage_type: FusionStage) -> PipelineStage:
    class StubStage(PipelineStage):
        @property
        def stage(self) -> FusionStage:
            return stage_type

        @property
        def name(self) -> str:
            return "StubStage"

        @property
        def version(self) -> str:
            return "0.0.0"

        def execute(self, ctx: FusionContext) -> FusionContext:
            return ctx

    return StubStage()


# ── Pipeline / Stage ─────────────────────


class TestFusionStage:
    def test_values(self) -> None:
        assert FusionStage.EXTRACTION.value == "extraction"
        assert FusionStage.NORMALIZATION.value == "normalization"
        assert FusionStage.ENTITY_RESOLUTION.value == "entity_resolution"
        assert FusionStage.CONFLICT_DETECTION.value == "conflict_detection"
        assert FusionStage.SOURCE_SCORING.value == "source_scoring"
        assert FusionStage.MERGE.value == "merge"
        assert FusionStage.DELTA.value == "delta"
        assert FusionStage.SELECTION.value == "selection"

    def test_order(self) -> None:
        stages = list(FusionStage)
        assert stages.index(FusionStage.ENTITY_RESOLUTION) < stages.index(FusionStage.CONFLICT_DETECTION)
        assert stages.index(FusionStage.NORMALIZATION) < stages.index(FusionStage.ENTITY_RESOLUTION)

    def test_unique(self) -> None:
        values = [s.value for s in FusionStage]
        assert len(values) == len(set(values))


class TestFusionPipeline:
    def test_create_with_engine(self) -> None:
        pipeline = FusionPipeline(
            _StubEngine(),
            _StubResolver(),
            _StubScorer(),
            _StubMerger(),
            _StubDetector(),
            _StubSelector(),
        )
        assert isinstance(pipeline.engine, FusionEngine)
        assert pipeline.stage_times == {}

    def test_run_with_engine(self) -> None:
        pipeline = FusionPipeline(
            _StubEngine(),
            _StubResolver(),
            _StubScorer(),
            _StubMerger(),
            _StubDetector(),
            _StubSelector(),
        )
        result = pipeline.run(bundle="ignored", documents=[])  # type: ignore[arg-type]
        assert result.accepted == ()

    def test_with_entity_resolver(self) -> None:
        pipeline = FusionPipeline(
            _StubEngine(),
            _StubResolver(),
            _StubScorer(),
            _StubMerger(),
            _StubDetector(),
            _StubSelector(),
            entity_resolver=_StubEntityResolver(),
        )
        assert pipeline.run(bundle="ignored", documents=[]).accepted == ()

    def test_create_with_stages(self) -> None:
        s = _make_stub_stage(FusionStage.EXTRACTION)
        pipeline = FusionPipeline(stages=[s])
        assert len(pipeline.stages) == 1
        assert pipeline.stages[0].stage == FusionStage.EXTRACTION
        assert pipeline.engine is None

    def test_run_with_stages(self) -> None:
        class S(PipelineStage):
            @property
            def stage(self) -> FusionStage:
                return FusionStage.MERGE

            @property
            def name(self) -> str:
                return "MergeStage"

            @property
            def version(self) -> str:
                return "1.0"

            def execute(self, ctx: FusionContext) -> FusionContext:
                ctx.facts = [
                    KnowledgeFact(
                        id=make_fact_id("A", "B", "C"),
                        subject="A",
                        predicate="B",
                        object="C",
                        confidence=0.9,
                    ),
                ]
                return ctx

        pipeline = FusionPipeline(stages=[S()])
        result = pipeline.run(bundle="ignored", documents=[])  # type: ignore[arg-type]
        assert len(result.accepted) == 1
        assert result.accepted[0].subject == "A"

    def test_register_stage(self) -> None:
        pipeline = FusionPipeline(stages=[])
        assert len(pipeline.stages) == 0
        pipeline.register_stage(_make_stub_stage(FusionStage.NORMALIZATION))
        assert len(pipeline.stages) == 1
        assert pipeline.stages[0].stage == FusionStage.NORMALIZATION

    def test_register_stage_at_index(self) -> None:
        s1 = _make_stub_stage(FusionStage.EXTRACTION)
        s2 = _make_stub_stage(FusionStage.MERGE)
        pipeline = FusionPipeline(stages=[s1, s2])
        mid = _make_stub_stage(FusionStage.ENTITY_RESOLUTION)
        pipeline.register_stage(mid, index=1)
        assert len(pipeline.stages) == 3
        assert pipeline.stages[0].stage == FusionStage.EXTRACTION
        assert pipeline.stages[1].stage == FusionStage.ENTITY_RESOLUTION
        assert pipeline.stages[2].stage == FusionStage.MERGE


# ── Registry ─────────────────────────────


class TestFusionRegistry:
    def test_initial_state(self) -> None:
        r = FusionRegistry()
        assert r.list_engines() == []
        assert r.list_conflict_resolvers() == []
        assert r.list_source_scorers() == []
        assert r.list_mergers() == []
        assert r.list_change_detectors() == []
        assert r.list_selectors() == []
        assert r.list_entity_resolvers() == []

    def test_register_and_get_engine(self) -> None:
        r = FusionRegistry()
        r.register_engine("default", _StubEngine())
        assert isinstance(r.get_engine("default"), FusionEngine)

    def test_get_missing_raises(self) -> None:
        r = FusionRegistry()
        try:
            r.get_engine("nonexistent")
            raise AssertionError
        except KeyError:
            pass

    def test_register_and_get_conflict_resolver(self) -> None:
        r = FusionRegistry()
        r.register_conflict_resolver("default", _StubResolver())
        assert isinstance(r.get_conflict_resolver("default"), ConflictResolver)

    def test_register_and_get_source_scorer(self) -> None:
        r = FusionRegistry()
        r.register_source_scorer("default", _StubScorer())
        assert isinstance(r.get_source_scorer("default"), SourceScorer)

    def test_register_and_get_merger(self) -> None:
        r = FusionRegistry()
        r.register_merger("default", _StubMerger())
        assert isinstance(r.get_merger("default"), KnowledgeMerger)

    def test_register_and_get_change_detector(self) -> None:
        r = FusionRegistry()
        r.register_change_detector("default", _StubDetector())
        assert isinstance(r.get_change_detector("default"), ChangeDetector)

    def test_register_and_get_selector(self) -> None:
        r = FusionRegistry()
        r.register_selector("default", _StubSelector())
        assert isinstance(r.get_selector("default"), MemoryCandidateSelector)

    def test_multiple_engines(self) -> None:
        r = FusionRegistry()
        r.register_engine("fast", _StubEngine())
        r.register_engine("deep", _StubEngine())
        assert len(r.list_engines()) == 2

    def test_register_and_get_entity_resolver(self) -> None:
        r = FusionRegistry()
        r.register_entity_resolver("default", _StubEntityResolver())
        assert isinstance(r.get_entity_resolver("default"), EntityResolver)
        assert r.list_entity_resolvers() == ["default"]

    def test_get_missing_entity_resolver_raises(self) -> None:
        r = FusionRegistry()
        try:
            r.get_entity_resolver("nonexistent")
            raise AssertionError
        except KeyError:
            pass


# ── Config ────────────────────────────────


class TestFusionConfig:
    def test_defaults(self) -> None:
        c = FusionConfig()
        assert c.enabled is True
        assert c.min_confidence_threshold == 0.3

    def test_mutable(self) -> None:
        c = FusionConfig()
        c.min_confidence_threshold = 0.5
        assert c.min_confidence_threshold == 0.5


# ── __init__ exports ──────────────────────


class TestExports:
    def test_all_symbols(self) -> None:
        exported = set(__import__("motor.core.fusion", fromlist=["*"]).__all__)
        expected = {
            "ChangeDetector",
            "Conflict",
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
            "ResolvedEntity",
            "ResolutionStatus",
            "SourceScore",
            "SourceScorer",
            "StageProvenance",
            "make_claim_id",
            "make_conflict_id",
            "make_fact_id",
        }
        assert exported == expected, f"Missing: {expected - exported}"
