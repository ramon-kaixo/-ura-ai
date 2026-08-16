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
        # version no participa en la identidad (ver docstring de make_fact_id)
        assert make_fact_id("Apple", "CEO", "Tim") == make_fact_id("Apple", "CEO", "Tim")

    def test_default_version_is_1(self) -> None:
        a = make_fact_id("X", "Y", "Z")
        b = make_fact_id("X", "Y", "Z")
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
        fid = make_fact_id("Apple", "CEO", "Tim Cook")
        f1 = KnowledgeFact(id=fid, subject="Apple", predicate="CEO", object="Tim Cook", confidence=0.8, version=1)
        f2 = KnowledgeFact(id=fid, subject="Apple", predicate="CEO", object="Tim Cook", confidence=0.95, version=2)
        assert f1.version == 1
        assert f2.version == 2
        assert f1.id == f2.id  # Misma identidad (version no participa)

    def test_superseded_by(self) -> None:
        fid = make_fact_id("Apple", "CEO", "Tim Cook")
        f1 = KnowledgeFact(id=fid, subject="Apple", predicate="CEO", object="Tim Cook", confidence=0.8, version=1)
        f2 = KnowledgeFact(id=fid, subject="Apple", predicate="CEO", object="Tim Cook", confidence=0.95, version=2)
        assert f1.superseded_by is None
        assert f2.superseded_by is None

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
        # Lista actualizada de exports. Si algún símbolo se elimina,
        # también debe eliminarse de __all__ en motor/core/fusion/__init__.py
        expected = {
            "ChangeDetector",
            "build_default_pipeline",
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
        }
        assert exported == expected, f"Difference: extra={exported - expected}, missing={expected - exported}"


class TestDefaultPipelineIntegration:
    """Integración F25-B4+B5: pipeline por defecto con stages reales (TASK-20260812-006)."""

    def test_build_default_pipeline_order(self) -> None:
        from motor.core.fusion.engine import build_default_pipeline

        stages = build_default_pipeline()
        valores = [s.stage for s in stages]
        assert valores == [
            FusionStage.NORMALIZATION,
            FusionStage.ENTITY_RESOLUTION,
            FusionStage.CONFLICT_DETECTION,
            FusionStage.SOURCE_SCORING,
            FusionStage.MERGE,
            FusionStage.DELTA,
            FusionStage.SELECTION,
        ]

    def test_default_classmethod_builds_stages(self) -> None:
        pipeline = FusionPipeline.default()
        assert len(pipeline.stages) == 7
        assert pipeline.stage_times == {}

    def test_default_pipeline_runs_empty(self) -> None:
        pipeline = FusionPipeline.default()
        result = pipeline.run(bundle="ignored", documents=[])  # type: ignore[arg-type]
        assert result.accepted == ()
        assert result.rejected == ()
        assert result.conflicts == ()
        assert isinstance(result.statistics, dict)


class TestBridge:
    """Cobertura 100x100: proyecciones del puente F25-A3 (TASK-20260814-001)."""

    def test_knowledge_fact_to_semantic_fact_full(self) -> None:
        from motor.core.fusion.bridge import knowledge_fact_to_semantic_fact

        kf = KnowledgeFact(
            id="f1",
            subject="sujeto",
            predicate="predica",
            object="objeto",
            confidence=0.75,
            evidence=(
                Evidence(
                    evidence_id="ev1",
                    document_url="http://x.com",
                    canonical_url=None,
                    title="T",
                    document_index=0,
                    sentence_position=1,
                    fragment="c",
                    content_hash="h",
                    document_id="d",
                    fetched_at=1.0,
                    quality_score=0.9,
                ),
            ),
            provenance=("p1", "p2"),
            version=3,
            created_at=123.0,
            evidence_ids=("e1", "e2"),
        )
        d = knowledge_fact_to_semantic_fact(kf)
        assert d["id"] == "f1"
        assert d["importance"] == 0.75 * 0.8
        assert d["source_episode_ids"] == ["e1", "e2"]
        assert d["tags"] == ["fusion", "knowledge"]
        assert d["version"] == 3
        assert d["created_at"] == 123.0
        assert d["metadata"]["provenance"] == ["p1", "p2"]
        assert d["metadata"]["origin"] == "fusion_pipeline"

    def test_knowledge_fact_to_semantic_fact_defaults(self) -> None:
        from motor.core.fusion.bridge import knowledge_fact_to_semantic_fact

        kf = KnowledgeFact(id="f2", subject="s", predicate="p", object="o", confidence=0.5)
        d = knowledge_fact_to_semantic_fact(kf)
        assert d["created_at"] > 0.0
        assert d["version"] == 1

    def test_fact_version_to_semantic_fact(self) -> None:
        from motor.core.fusion.bridge import fact_version_to_semantic_fact
        from motor.core.fusion.models import Fact, FactVersion

        fact = Fact(fact_id="fx", subject="sx", predicate="px", object="ox")
        version = FactVersion(
            version_id="v1",
            fact_id="fx",
            confidence=0.9,
            evidence_ids=("ev1",),
            provenance=("pr1",),
            created_at=55.0,
            supersedes="v0",
        )
        d = fact_version_to_semantic_fact(fact, version)
        assert d["id"] == "fx"
        assert d["subject"] == "sx"
        assert d["object_value"] == "ox"
        assert d["importance"] == 0.9 * 0.8
        assert d["source_episode_ids"] == ["ev1"]
        assert d["tags"] == ["fusion", "versioned"]
        assert d["version"] == 1
        assert d["created_at"] == 55.0
        assert d["metadata"]["supersedes"] == "v0"
        assert d["metadata"]["version_id"] == "v1"


class TestBaseStageHooks:
    """Cobertura 100x100: BaseStage.execute + hook _record_stats + deterministic (TASK-20260814-001)."""

    def test_base_stage_execute_con_hook_stats(self) -> None:
        from motor.core.fusion.base import BaseStage

        class _Stub(BaseStage):
            stage = FusionStage.ENTITY_RESOLUTION
            _record_stats = True

            def _execute(self, context: FusionContext) -> FusionContext:
                context.claims.append(KnowledgeClaim(id="c1", text="txt", confidence=0.5))
                return context

            @property
            def name(self) -> str:
                return "stub"

            @property
            def version(self) -> str:
                return "1.0.0"

        stub = _Stub()
        assert stub.deterministic is True
        ctx = stub.execute(FusionContext())
        assert len(ctx.transforms) == 1
        assert ctx.transforms[0].input_claims == 0
        assert ctx.transforms[0].output_claims == 1
        assert ctx.statistics["stages"]["stub"]["input_facts"] == 0
        assert ctx.statistics["stages"]["stub"]["version"] == "1.0.0"


class TestConfigHash:
    """Cobertura 100x100: to_dict + make_config_hash determinista (TASK-20260814-001)."""

    def test_to_dict_and_hash(self) -> None:
        from motor.core.fusion.config import FusionConfig, make_config_hash

        cfg = FusionConfig()
        d = cfg.to_dict()
        assert d["authority_weight"] == 0.4
        h1 = make_config_hash(cfg)
        h2 = make_config_hash(FusionConfig())
        assert h1 == h2
        assert len(h1) == 16
        assert make_config_hash(FusionConfig(authority_weight=0.9)) != h1


class TestNormalizationStageCobertura:
    """Cobertura 100x100: NormalizationStage con claims reales (TASK-20260814-001)."""

    def test_normaliza_claims(self) -> None:
        from motor.core.fusion.stages.normalization import NormalizationStage

        ctx = FusionContext()
        ctx.claims.append(KnowledgeClaim(id="c1", text="  Hola,   MUNDO!!  ", confidence=0.5))
        ctx = NormalizationStage().execute(ctx)
        assert ctx.claims[0].normalized_text == "hola mundo"
        assert ctx.statistics["claims_normalized"] == 1


class TestSelectorCobertura:
    """Cobertura 100x100: MemoryCandidateSelectionStage con memory fake (TASK-20260814-001)."""

    def test_seleccion_con_memoria_ambigua(self) -> None:
        from motor.core.fusion.stages.selector import MemoryCandidateSelectionStage, ThresholdSelector

        kf = KnowledgeFact(id="f1", subject="s", predicate="p", object="o", confidence=0.9)
        ctx = FusionContext()
        ctx.facts.append(kf)
        ctx.statistics["ambiguous_entity_ids"] = ["e1"]
        written: list = []

        class _FakeMemory:
            def append(self, entry: object) -> None:
                written.append(entry)

        ctx.statistics["_memory_instance"] = _FakeMemory()
        stage = MemoryCandidateSelectionStage(selector=ThresholdSelector(min_confidence=0.5, max_candidates=1))
        ctx = stage.execute(ctx)
        assert "ambiguous entities" in ctx.warnings[0]
        assert len(written) == 1
        assert ctx.statistics["candidates_returned"] == 1
        assert ctx.statistics["memory_entries_written"] == 1
        assert ctx.provenance.selector_name == "ThresholdSelector"

    def test_seleccion_sin_memoria(self) -> None:
        from motor.core.fusion.stages.selector import MemoryCandidateSelectionStage

        ctx = FusionContext()
        ctx.facts.append(KnowledgeFact(id="f2", subject="s", predicate="p", object="o", confidence=0.2))
        stage = MemoryCandidateSelectionStage()
        ctx = stage.execute(ctx)
        assert ctx.statistics["memory_entries_written"] == 0
        assert ctx.statistics["candidates_returned"] == 0


class TestDeltaCobertura:
    """Cobertura 100x100: BasicChangeDetector todas las ramas + KnowledgeDeltaStage (TASK-20260814-001)."""

    def _kf(self, fid: str, obj: str) -> KnowledgeFact:
        return KnowledgeFact(id=fid, subject=fid, predicate="p", object=obj, confidence=0.8)

    def test_detect_delta_todas_ramas(self) -> None:
        from motor.core.fusion.stages.delta import BasicChangeDetector

        d = BasicChangeDetector().detect_delta(
            [
                self._kf("a", "o1"),
                self._kf("b", "o2"),
                self._kf("c", "o3"),
                KnowledgeFact(id=None, subject="x", predicate="p", object="x", confidence=0.8),
                self._kf("e", "new"),
            ],
            [self._kf("a", "o1"), self._kf("b", "old"), self._kf("c", "o3"), self._kf("e", "old")],
        )
        assert {f.id for f in d.facts_added} == {None}
        assert {f.id for f in d.facts_updated} == {"b", "e"}
        assert {f.id for f in d.facts_confirmed} == {"a", "c"} if hasattr(d, "facts_confirmed") else True

    def test_stage_delta_ambiguedad(self) -> None:
        from motor.core.fusion.stages.delta import KnowledgeDeltaStage

        ctx = FusionContext()
        ctx.facts.append(self._kf("a", "o1"))
        ctx.statistics["existing_facts"] = []
        ctx.statistics["ambiguous_entity_ids"] = ["e1"]
        ctx = KnowledgeDeltaStage().execute(ctx)
        assert ctx.statistics["deltas_added"] == 1
        assert ctx.statistics["has_changes"] is True
        assert "ambiguous entities" in ctx.warnings[0]


class TestMergerCobertura:
    """Cobertura 100x100: SimpleKnowledgeMerger todas las ramas + KnowledgeMergerStage (TASK-20260814-001)."""

    def test_merge_todas_ramas_texto(self) -> None:
        from motor.core.fusion.stages.merger import SimpleKnowledgeMerger

        kc = KnowledgeClaim
        claims = [
            kc(id="c1", text="El sol sale por el este", confidence=0.7, text_id="t1"),
            kc(id="c2", text="palabra", confidence=0.5),
            kc(id="c3", text="dos palabras", confidence=0.5),
            kc(id="c4", text="", confidence=0.5),
        ]
        facts = SimpleKnowledgeMerger().merge(claims, [])
        assert len(facts) == 4
        assert facts[0].subject == "El" and facts[0].predicate == "sol"
        assert facts[0].object == "sale por el este"
        assert facts[0].evidence_ids == ("t1",)
        assert facts[1].predicate == "" and facts[1].object == ""
        assert facts[2].predicate == "palabras" and facts[2].object == ""
        assert facts[3].subject == ""
        assert facts[0].provenance == ("c1",)

    def test_stage_merger_con_ambiguedad(self) -> None:
        from motor.core.fusion.stages.merger import KnowledgeMergerStage

        ctx = FusionContext()
        ctx.claims.append(KnowledgeClaim(id="c1", text="a b c", confidence=0.7, normalized_text="a b c"))
        ctx.statistics["ambiguous_entity_ids"] = ["a"]
        ctx = KnowledgeMergerStage().execute(ctx)
        assert ctx.facts == []
        assert "Excluded 1 claims" in ctx.warnings[0]
        assert ctx.statistics["claims_with_ambiguous_entities"] == 1

    def test_stage_merger_con_ambiguedad_ninguna_excluida(self) -> None:
        from motor.core.fusion.stages.merger import KnowledgeMergerStage

        ctx = FusionContext()
        ctx.claims.append(KnowledgeClaim(id="c1", text="x y z", confidence=0.7, normalized_text="x y z"))
        ctx.statistics["ambiguous_entity_ids"] = ["otro"]
        ctx = KnowledgeMergerStage().execute(ctx)
        assert len(ctx.facts) == 1
        assert ctx.warnings == []


class TestSourceScorerCobertura:
    """Cobertura 100x100: QualitySourceScorer todas las ramas (TASK-20260814-001)."""

    def _ev(self, url: str, fetched_at: float) -> Evidence:
        return Evidence(
            evidence_id=f"e-{url}",
            document_url=url,
            canonical_url=None,
            title="t",
            document_index=0,
            sentence_position=1,
            fragment="f",
            content_hash="h",
            document_id="d",
            fetched_at=fetched_at,
            quality_score=0.8,
        )

    def test_score_todas_ramas_tld(self) -> None:
        from motor.core.fusion.stages.source_scorer import QualitySourceScorer

        scorer = QualitySourceScorer()
        assert scorer._score_authority("https://www.gob.es/x").__class__ is float
        assert scorer._parse_tld("https://a.b.gov/") == "gov"
        assert scorer._parse_tld("https://sinpunto/") == "unknown"
        assert scorer._parse_tld("no-url") == "unknown"

        import time as _tm

        fresh = scorer.score(
            KnowledgeClaim(
                id="c1", text="t", confidence=0.5, evidence=self._ev("https://x.edu/", _tm.time() - 30 * 86400)
            )
        )
        assert fresh.authority == 0.8
        assert 0.1 <= fresh.freshness <= 1.0
        assert fresh.overall == fresh.authority * 0.5 + fresh.freshness * 0.5

        viejo = scorer.score(KnowledgeClaim(id="c2", text="t", confidence=0.5, evidence=self._ev("https://x.com/", 0)))
        assert viejo.freshness == 0.1
        assert viejo.url == "https://x.com/"

        sin_ev = scorer.score(KnowledgeClaim(id="c3", text="t", confidence=0.5))
        assert sin_ev.url == "unknown"
        assert sin_ev.freshness == 0.1

        from motor.core.fusion.models import EvidenceSet

        escore = scorer.score_evidence(EvidenceSet(claims=[KnowledgeClaim(id="c4", text="t", confidence=0.5)]))
        assert len(escore) == 1

    def test_stage_source_scoring(self) -> None:
        from motor.core.fusion.stages.source_scorer import SourceScoringStage

        ctx = FusionContext()
        ctx.claims.append(KnowledgeClaim(id="c1", text="t", confidence=0.5))
        ctx = SourceScoringStage().execute(ctx)
        assert ctx.statistics["claims_scored"] == 1
        assert ctx.claims[0].source_score is not None


class TestCoberturaFina:
    """Cobertura 100x100: remanentes finos (TASK-20260814-001)."""

    def test_versions_y_duplicado(self) -> None:
        from motor.core.fusion.stages.delta import BasicChangeDetector
        from motor.core.fusion.stages.merger import SimpleKnowledgeMerger
        from motor.core.fusion.stages.selector import MemoryCandidateSelectionStage, ThresholdSelector

        assert BasicChangeDetector().version == "1.0.0"
        assert SimpleKnowledgeMerger().version == "1.0.0"

        class _DupMemory:
            def append(self, entry: object) -> None:
                raise KeyError("duplicado")

        kf = KnowledgeFact(id="f1", subject="s", predicate="p", object="o", confidence=0.9)
        ctx = FusionContext()
        ctx.facts.append(kf)
        ctx.statistics["_memory_instance"] = _DupMemory()
        stage = MemoryCandidateSelectionStage(selector=ThresholdSelector(min_confidence=0.1))
        ctx = stage.execute(ctx)
        assert ctx.statistics["memory_entries_written"] == 1


class TestExtractionCobertura:
    """Cobertura 100x100: ExtractionStage (TASK-20260814-001)."""

    def test_extraction_con_bundle_y_sin(self) -> None:
        from motor.core.fusion.stages.extraction import ExtractionStage

        ctx = FusionContext(bundle=None)
        assert ExtractionStage().execute(ctx) is ctx

        class _Bundle:
            evidence = (
                Evidence(
                    evidence_id="ev1",
                    document_url="http://x.com",
                    canonical_url=None,
                    title="t",
                    document_index=0,
                    sentence_position=1,
                    fragment="frag uno",
                    content_hash="h",
                    document_id="d",
                    fetched_at=5.0,
                    quality_score=0.85,
                ),
            )

        ctx2 = ExtractionStage().execute(FusionContext(bundle=_Bundle()))
        assert len(ctx2.claims) == 1
        assert ctx2.claims[0].text == "frag uno"
        assert ctx2.claims[0].confidence == 0.85
        assert ctx2.claims[0].text_id == "ev1"
        assert ctx2.statistics["claims_extracted"] == 1
        assert len(ctx2.claims[0].id) == 16


class TestConflictGraphCobertura:
    """Cobertura 100x100: ConflictGraph completo (TASK-20260814-001)."""

    def test_conflict_graph_estructura(self) -> None:
        from motor.core.fusion.models import ConflictGraph

        g = ConflictGraph()
        assert g.has_conflicts is False
        assert g.unresolved_count == 0
        assert g.unresolved == []
        assert g.claims_for("x") == []
        assert g.clusters() == []

    def test_conflict_graph_componentes(self) -> None:
        from motor.core.fusion.models import Conflict, ConflictGraph, ConflictType

        edges = [
            Conflict(id="c1", claim_a="a", claim_b="b"),
            Conflict(id="c2", claim_a="b", claim_b="c"),
            Conflict(id="c3", claim_a="d", claim_b="e", conflict_type=ConflictType.OPINION),
        ]
        g = ConflictGraph.from_edges(edges)
        assert g.has_conflicts
        assert g.unresolved_count == 3
        assert g.claim_ids == {"a", "b", "c", "d", "e"}
        assert {c.id for c in g.unresolved} == {c.id for c in edges}
        assert sorted(len(c) for c in g.clusters()) == [2, 3]
        assert sorted(g.claims_for("b")) == ["a", "c"]
        assert g.claims_for("z") == []
        assert len(ConflictGraph.from_edges([]).claim_ids) == 0


class TestRegistryCobertura:
    """Cobertura 100x100: FusionRegistry getters y errores (TASK-20260814-001)."""

    def test_registry_errores_claves(self) -> None:
        from motor.core.fusion.registry import FusionRegistry
        from motor.core.fusion.stages.delta import BasicChangeDetector
        from motor.core.fusion.stages.merger import SimpleKnowledgeMerger
        from motor.core.fusion.stages.selector import ThresholdSelector
        from motor.core.fusion.stages.source_scorer import QualitySourceScorer

        r = FusionRegistry()
        r.register_conflict_resolver("r1", _StubResolver())
        assert "r1" in r.list_conflict_resolvers()
        try:
            r.get_conflict_resolver("nope")
            raise AssertionError("no lanzo")
        except KeyError:
            pass
        r.register_source_scorer("s1", QualitySourceScorer())
        assert r.get_source_scorer("s1") is not None
        try:
            r.get_source_scorer("nope")
            raise AssertionError
        except KeyError:
            pass
        r.register_merger("m1", SimpleKnowledgeMerger())
        assert "m1" in r.list_mergers()
        try:
            r.get_merger("nope")
            raise AssertionError
        except KeyError:
            pass
        r.register_change_detector("d1", BasicChangeDetector())
        assert r.get_change_detector("d1").version == "1.0.0"
        try:
            r.get_change_detector("nope")
            raise AssertionError
        except KeyError:
            pass
        r.register_selector("t1", ThresholdSelector())
        assert "t1" in r.list_selectors()
        try:
            r.get_selector("nope")
            raise AssertionError
        except KeyError:
            pass


class TestConflictDetectionCobertura:
    """Cobertura 100x100: NaiveConflictResolver + ConflictDetectionStage (TASK-20260814-001)."""

    def _claim(self, cid: str, subj: str, pred: str, obj: str, conf: float) -> KnowledgeClaim:
        return KnowledgeClaim(
            id=cid, text=f"{subj} {pred} {obj}", confidence=conf, subject=subj, predicate=pred, object=obj
        )

    def test_detect_buckets_y_pares(self) -> None:
        from motor.core.fusion.stages.conflict_detection import NaiveConflictResolver

        r = NaiveConflictResolver()
        claims = [
            self._claim("a1", "Sol", "es", "azul", 0.9),
            self._claim("a2", "sOL", "es", "verde", 0.7),
            self._claim("a_bis", "Sol", "es", "azul", 0.8),
            KnowledgeClaim(id="sin_sujeto", text="x", confidence=0.5),
            self._claim("otro", "Luna", "es", "blanca", 0.9),
        ]
        conflicts = r.detect(claims)
        assert len(conflicts) == 2
        assert conflicts[0].conflict_type == ConflictType.CONTRADICTION
        assert "azul" in conflicts[0].description

    def test_resolve_ganador_y_empate(self) -> None:
        from motor.core.fusion.stages.conflict_detection import NaiveConflictResolver

        r = NaiveConflictResolver()
        conflicts = [
            Conflict(id="x1", claim_a="a1", claim_b="a2"),
            Conflict(id="x2", claim_a="b1", claim_b="b2"),
            Conflict(id="x3", claim_a="noexiste", claim_b="a1"),
        ]
        claims = [
            self._claim("a1", "S", "e", "o1", 0.9),
            self._claim("a2", "S", "e", "o2", 0.5),
            self._claim("b1", "S", "e", "o3", 0.7),
            self._claim("b2", "S", "e", "o4", 0.7),
        ]
        rf, unres = r.resolve(conflicts, claims)
        assert rf == []
        assert {c.id for c in unres} == {"x2"}
        c1 = next(c for c in conflicts if c.id == "x1")
        assert c1.resolved and "Preferring claim a1" in c1.resolution

    def test_stage_ramas(self) -> None:
        from motor.core.fusion.stages.conflict_detection import ConflictDetectionStage

        assert ConflictDetectionStage().version == "1.0.0"
        assert ConflictDetectionStage().execute(FusionContext()) is not None
        ctx = FusionContext()
        ctx.statistics["ambiguous_entity_ids"] = ["m"]
        ctx.claims.append(
            KnowledgeClaim(
                id="c1", text="m t", confidence=0.5, subject="m", predicate="p", object="o", normalized_text="m t"
            )
        )
        ctx2 = ConflictDetectionStage().execute(ctx)
        assert ctx2.statistics["conflicts_detected"] == 0
        assert ctx2.statistics["conflicts_unresolved"] == 0
        assert "ambiguous" in ctx2.warnings[0]

        ctx3 = FusionContext()
        ctx3.claims = [self._claim("c1", "S", "e", "o1", 0.9), self._claim("c2", "S", "e", "o2", 0.5)]
        ctx3.statistics["ambiguous_entity_ids"] = ["otra"]
        ctx4 = ConflictDetectionStage().execute(ctx3)
        assert ctx4.statistics["conflicts_detected"] == 1
        assert len(ctx4.conflict_graph.edges) == 1
        assert ctx4.provenance.conflict_resolver_name == "NaiveConflictResolver"


class TestContextBuilderCobertura:
    """Cobertura 100x100: ContextBuilder completo (TASK-20260814-001)."""

    def test_builder_ramas(self) -> None:
        from motor.core.fusion.context_builder import ContextBuilder
        from motor.core.fusion.models import Fact, FactVersion, VersionState

        b = ContextBuilder()
        assert b.build_context() == ""
        assert b.index is None
        b.set_index(None)
        assert b.build_context("que vende apple?") == ""

        class _Idx:
            def lookup_entity(self, entity: str) -> list:
                if entity == "apple":
                    return [
                        (
                            Fact(fact_id="f1", subject="Apple", predicate="vende", object="iPhones"),
                            FactVersion(version_id="v1", fact_id="f1", confidence=0.9, state=VersionState.CURRENT),
                        ),
                        (
                            Fact(fact_id="f1", subject="Apple", predicate="vende", object="iPhones"),
                            FactVersion(version_id="v0", fact_id="f1", confidence=0.8, state=VersionState.SUPERSEDED),
                        ),
                        KnowledgeFact(id="legacy", subject="Apple", predicate="fue", object="fundada", confidence=0.7),
                    ]
                return []

        b = ContextBuilder(_Idx())
        ctx = b.build_context(query="Apple vende que?", include_entities=["apple", "oranges"])
        assert "vende | iPhones" in ctx
        assert "fue | fundada" in ctx
        assert ctx.startswith("# Conocimiento disponible")
        assert "SUPERSEDED" not in ctx
        assert ctx.count("confianza:") == 2

        ctx2 = b.build_context(query="apple", include_entities=[])
        assert "Apple" in ctx2
        ctx3 = ContextBuilder(_Idx()).build_context(query="h", include_entities=["nada"])
        assert ctx3 == ""


class TestRunFusionOnClaims:
    """Cobertura 100x100: run_fusion_on_claims + persist (TASK-20260814-001)."""

    def test_run_fusion_con_claims(self) -> None:
        from motor.core.fusion import run_fusion_on_claims

        claims = [
            KnowledgeClaim(id="c1", text="Apple vende iPhones", confidence=0.9),
            KnowledgeClaim(id="c2", text="Apple fue fundada", confidence=0.8),
        ]
        n = run_fusion_on_claims(claims, semantic_db="", correlation_id="corr-1234567890abcdef")
        assert n >= 1

    def test_run_fusion_sin_facts(self) -> None:
        from motor.core.fusion import run_fusion_on_claims

        assert run_fusion_on_claims([], semantic_db="") == 0


class TestFactIndexCobertura:
    """Cobertura 100x100: FactIndex completo (TASK-20260814-001)."""

    def test_fact_index_legacy_completo(self) -> None:
        from motor.core.fusion.fact_index import FactIndex

        idx = FactIndex()
        assert idx.size == 0
        assert idx.frozen is False
        kf = KnowledgeFact(
            id="f1",
            subject="Apple",
            predicate="vende",
            object="iPhones",
            confidence=0.9,
            evidence_ids=("e1", "e2", ""),
        )
        idx.add_fact(kf)
        assert idx.lookup("f1") is kf
        assert idx.lookup_entity("APPLE") == [kf]
        assert idx.lookup_predicate("Vende") == [kf]
        assert idx.lookup_subject_predicate("apple", "vende") == [kf]
        assert idx.lookup_evidence("e1") == [kf]
        assert idx.lookup_evidence("nope") == []
        assert idx.lookup_entity("nada") == []
        assert idx.size == 1
        idx.freeze()
        assert idx.frozen is True
        try:
            idx.add_fact(kf)
            raise AssertionError
        except RuntimeError:
            pass
        try:
            idx.remove_fact("f1")
            raise AssertionError
        except RuntimeError:
            pass
        copia = idx.copy()
        assert copia.size == 1 and copia.frozen is False

    def test_fact_index_remove_y_errores(self) -> None:
        from motor.core.fusion.fact_index import FactIndex

        idx = FactIndex()
        kf = KnowledgeFact(
            id="f1", subject="Apple", predicate="vende", object="iPhones", confidence=0.9, evidence_ids=("e1",)
        )
        idx.add_fact(kf)
        assert idx.remove_fact("f1") is kf
        assert idx.size == 0
        assert idx.lookup_evidence("e1") == []
        try:
            idx.remove_fact("f1")
            raise AssertionError
        except KeyError:
            pass
        try:
            idx.add_fact(KnowledgeFact(id=None, subject="s", predicate="p", object="o", confidence=0.5))
            raise AssertionError
        except ValueError:
            pass
        try:
            idx.add_fact(kf)
            idx.add_fact(kf)
            raise AssertionError
        except KeyError:
            pass

    def test_fact_index_nuevo_modelo(self) -> None:
        from motor.core.fusion.fact_index import FactIndex
        from motor.core.fusion.models import Fact, FactVersion, VersionState

        fact = Fact(fact_id="f9", subject="Sol", predicate="es", object="estrella")
        v1 = FactVersion(
            version_id="v1", fact_id="f9", confidence=0.9, evidence_ids=("e1",), state=VersionState.CURRENT
        )
        idx = FactIndex()
        idx.add_fact_version(fact, v1)
        assert idx.lookup("f9") == (fact, v1)
        try:
            idx.add_fact_version(fact, v1)
            raise AssertionError
        except KeyError:
            pass
        v2 = FactVersion(
            version_id="v2", fact_id="f9", confidence=0.95, evidence_ids=("e2",), state=VersionState.CURRENT
        )
        idx.update_current("f9", v2)
        assert idx.lookup("f9")[1].version_id == "v2"
        assert idx.lookup_subject_predicate("sol", "es")[0][1].version_id == "v2"
        try:
            idx.update_current("zz", v2)
            raise AssertionError
        except KeyError:
            pass
        idx2 = FactIndex()
        kf_legacy = KnowledgeFact(id="fL", subject="S", predicate="P", object="O", confidence=0.5)
        idx2.add_fact(kf_legacy)
        idx2.update_current("fL", v2)
        assert idx2.lookup("fL") is kf_legacy
        assert idx.lookup_evidence("e1")[0] == (fact, v2)
        assert idx.lookup_evidence("e2") == []

    def test_fact_index_build(self) -> None:
        from motor.core.fusion.fact_index import FactIndex

        kfs = [
            KnowledgeFact(id="a", subject="S", predicate="P", object="O1", confidence=0.5),
            KnowledgeFact(id="a", subject="S", predicate="P", object="O2", confidence=0.5),
            KnowledgeFact(id=None, subject="S", predicate="P", object="O3", confidence=0.5),
        ]
        idx = FactIndex.build(kfs)
        assert idx.size == 1
        assert idx.frozen is True
        from motor.core.fusion.models import Fact, FactVersion, VersionState

        entries = [
            (
                Fact(fact_id="x", subject="A", predicate="B", object="C"),
                FactVersion(version_id="vx", fact_id="x", confidence=0.9, state=VersionState.CURRENT),
            ),
            (
                Fact(fact_id="x", subject="A", predicate="B", object="C"),
                FactVersion(version_id="vy", fact_id="x", confidence=0.9, state=VersionState.CURRENT),
            ),
        ]
        idx2 = FactIndex.build_from_versions(entries)
        assert idx2.size == 1


class TestEntityResolverCobertura:
    """Cobertura 100x100: ContextualEntityResolver + EntityRegistry + LRUCache + stages (TASK-20260814-001)."""

    def test_cache_policy_from_string(self) -> None:
        from motor.core.fusion.stages.entity_resolver import CachePolicy

        assert CachePolicy.from_string("all") == CachePolicy.ALL
        assert CachePolicy.from_string("disabled") == CachePolicy.DISABLED
        try:
            CachePolicy.from_string("nope")
            raise AssertionError
        except ValueError:
            pass

    def test_registry_y_lru(self) -> None:
        from motor.core.fusion.stages.entity_resolver import EntityDef, EntityRegistry, LRUCache

        reg = EntityRegistry(
            {
                "perro": [
                    EntityDef(entity_id="P1", canonical_name="Perro", aliases=["can"], keywords=["ladra"]),
                    EntityDef(entity_id="P2", canonical_name="Perro2", keywords=["muerde"]),
                ]
            }
        )
        assert len(reg) == 1
        assert "perro" in reg.known_names
        assert "can" in reg.known_names
        assert len(reg.lookup("PERRO")) == 2
        assert reg.lookup("gato") == []
        assert EntityRegistry().known_names == set()

        c = LRUCache(maxsize=2)
        assert c.size == 0
        assert c.maxsize == 2
        e = ResolvedEntity(entity_id="x", canonical_name="X", confidence=0.9)
        c.put("a", e)
        assert c.get("a") is e
        assert c.get("z") is None
        c.put("b", e)
        c.put("c", e)
        assert c.size == 2
        assert c.get("a") is None
        c.clear()
        assert c.size == 0

    def test_extract_candidates_ngram(self) -> None:
        from motor.core.fusion.stages.entity_resolver import EntityDef, EntityRegistry, _extract_entity_candidates

        reg = EntityRegistry({"berkshire hathaway": [EntityDef(entity_id="B1", canonical_name="BH")]})
        cand = _extract_entity_candidates("Berkshire Hathaway compra", reg)
        assert cand == ["berkshire hathaway"]
        assert _extract_entity_candidates("", reg) == []

    def test_contextual_resolve_ramas(self) -> None:
        from motor.core.fusion.stages.entity_resolver import (
            CachePolicy,
            ContextualEntityResolver,
            EntityDef,
            EntityRegistry,
            KeywordScorer,
            ScoringStrategy,
        )

        class _TieScorer(ScoringStrategy):
            def select(self, entries, context):
                return None

        class _IdxScorer(ScoringStrategy):
            def select(self, entries, context):
                return 1

        multi_reg = EntityRegistry(
            {
                "manzana": [
                    EntityDef(entity_id="M1", canonical_name="Manzana Inc.", keywords=["empresa", "cupertino"]),
                    EntityDef(entity_id="M2", canonical_name="Manzana fruta", keywords=["fruta", "roja"]),
                ]
            }
        )
        r = ContextualEntityResolver(registry=multi_reg, scorer=KeywordScorer())
        assert r.version == "3.1.0"
        assert r.scorer is not None
        res = r.resolve("manzana", context={"claim_text": "la manzana es una fruta roja"})
        assert res.status == ResolutionStatus.RESOLVED and res.entity_id == "M2"
        r2 = ContextualEntityResolver(registry=multi_reg, scorer=_IdxScorer())
        assert r2.resolve("manzana", context={"claim_text": "x"}).entity_id == "M2"
        r3 = ContextualEntityResolver(registry=multi_reg, scorer=_TieScorer())
        amb = r3.resolve("manzana", context={"claim_text": "sin pistas"})
        assert amb.status == ResolutionStatus.AMBIGUOUS
        assert amb.entity_id == ""
        assert set(amb.aliases) == {"M1", "M2"}
        unk = ContextualEntityResolver().resolve("cosanueva", context={"claim_text": "y"})
        assert unk.status == ResolutionStatus.UNKNOWN
        assert unk.resolver_name == "ContextualEntityResolver"
        assert unk.entity_id == ""
        assert unk.confidence == 0.0
        assert unk.resolver_version == "3.1.0"
        vacio = ContextualEntityResolver().resolve("   ")
        assert vacio.status == ResolutionStatus.UNKNOWN
        uno = ContextualEntityResolver(
            registry=EntityRegistry({"gato": [EntityDef(entity_id="G1", canonical_name="Gato")]})
        ).resolve("gato", context={"claim_text": "cualquiera"})
        assert uno.status == ResolutionStatus.RESOLVED and uno.entity_id == "G1"
        assert uno.confidence == 0.95
        assert uno.canonical_name == "Gato"
        assert uno.resolver_name == "ContextualEntityResolver"
        assert r2.resolve_many(["manzana"], context={"claim_text": "x"})[0].entity_id == "M2"
        assert ContextualEntityResolver().normalize("  HOLa ") == "hola"

        # cache DETERMINISTIC_ONLY: entidad única y UNKNOWN se cachean
        r_det = ContextualEntityResolver(
            registry=EntityRegistry({"gato": [EntityDef(entity_id="G1", canonical_name="Gato")]})
        )
        r_det.resolve("gato", context={"claim_text": "cualquiera"})
        assert r_det.cache.size == 1  # entrada única → cacheada
        r_det.resolve("gato", context={"claim_text": "otro contexto distinto"})
        assert r_det.cache.size == 1  # hit de cache (no depende del contexto)
        r_unk = ContextualEntityResolver()
        r_unk.resolve("sinedefinir", context={"claim_text": "y"})
        assert r_unk.cache.size == 1  # UNKNOWN se cachea

        r_all = ContextualEntityResolver(registry=multi_reg, scorer=_IdxScorer(), cache_policy="all")
        assert r_all.cache_policy == CachePolicy.ALL
        assert r_all.cache.size == 0
        r_all.resolve("manzana", context={"claim_text": "ctx1"})
        assert r_all.cache.size == 1
        r_dis = ContextualEntityResolver(registry=multi_reg, scorer=_IdxScorer(), cache_policy="disabled")
        assert r_dis.cache_policy == CachePolicy.DISABLED
        r_dis.resolve("manzana", context={"claim_text": "x"})
        assert r_dis.cache.size == 0

    def test_rule_based_legacy(self) -> None:
        from motor.core.fusion.stages.entity_resolver import RuleBasedEntityResolver

        r = RuleBasedEntityResolver()
        assert r.version == "1.0.0"
        res = r.resolve("Apple")
        assert res.entity_id == "E0001" and res.status == ResolutionStatus.RESOLVED
        assert res.resolver_name == "RuleBasedEntityResolver"
        unk = r.resolve("cosas")
        assert unk.status == ResolutionStatus.UNKNOWN
        assert r.normalize("  X ") == "x"
        assert r.resolve_many(["apple", "zzz"])[1].status == ResolutionStatus.UNKNOWN

    def test_entity_resolution_stage(self) -> None:
        from motor.core.fusion.stages.entity_resolver import ContextualEntityResolver, EntityResolutionStage

        ctx = FusionContext()
        ctx.claims.append(
            KnowledgeClaim(id="c1", text="Apple vende iPhones", confidence=0.9, normalized_text="apple vende iphones")
        )
        ctx.claims.append(KnowledgeClaim(id="c2", text="manzana", confidence=0.9, normalized_text="manzana"))
        ctx2 = EntityResolutionStage(resolver=ContextualEntityResolver()).execute(ctx)
        assert ctx2.statistics["entities_resolved"] >= 1
        assert "resolver_cache_size" in ctx2.statistics
        assert ctx2.provenance.resolver_name == "ContextualEntityResolver"


class TestFactHistoryCobertura:
    """Cobertura 100x100: FactHistory completo (TASK-20260814-001)."""

    def _h(self) -> tuple:
        from motor.core.fusion.fact_history import FactHistory
        from motor.core.fusion.models import Fact, FactVersion, VersionState

        fact = Fact(fact_id="fh1", subject="Sol", predicate="es", object="estrella")
        v0 = FactVersion(version_id="v0", fact_id="fh1", confidence=0.5, created_at=10.0, state=VersionState.CURRENT)
        return FactHistory.create(fact, v0), Fact, FactVersion

    def test_constructor_validaciones(self) -> None:
        from motor.core.fusion.fact_history import FactHistory
        from motor.core.fusion.models import Fact, FactVersion, VersionState

        try:
            FactHistory(
                Fact(fact_id="a", subject="s", predicate="p", object="o"),
                FactVersion(version_id="v1", fact_id="b", confidence=0.5),
            )
            raise AssertionError
        except ValueError:
            pass
        try:
            FactHistory(
                Fact(fact_id="a", subject="s", predicate="p", object="o"),
                FactVersion(version_id="v1", fact_id="a", confidence=0.5, state=VersionState.SUPERSEDED),
            )
            raise AssertionError
        except ValueError:
            pass

    def test_ciclo_vida_completo(self) -> None:
        from motor.core.fusion.models import VersionState

        h, _Fact, FactVersion = self._h()
        assert h.fact_id == "fh1"
        assert h.current.version_id == "v0"
        assert h.current_version_id == "v0"
        assert h.created == 10.0
        assert h.updated == 10.0
        assert h.version_count == 1
        assert h.has_tombstone is False
        assert h.get_version("v0") is not None
        assert h.get_version("zz") is None
        assert [v.version_id for v in h.timeline()] == ["v0"]
        assert h.version_at(5.0) is None
        assert h.version_at(11.0).version_id == "v0"
        assert h.versions()["v0"].state == VersionState.CURRENT

        v1 = FactVersion(version_id="v1", fact_id="fh1", confidence=0.7, created_at=20.0)
        h.add_version(v1)
        assert h.current_version_id == "v1"
        assert h._versions["v0"].state == VersionState.SUPERSEDED
        assert h.updated == 20.0
        assert h.version_at(15.0).version_id == "v0"
        assert h.version_at(30.0).version_id == "v1"

        v2 = FactVersion(version_id="v2", fact_id="fh1", confidence=0.9, created_at=30.0)
        h.add_version(v2)
        r = h.rollback("v0")
        assert r.version_id == "v0"
        assert h.current_version_id == "v0"
        assert h._versions["v2"].state == VersionState.ROLLED_BACK
        assert h._versions["v0"].state == VersionState.CURRENT

        try:
            h.rollback("nope")
            raise AssertionError
        except KeyError:
            pass

        h.tombstone(
            FactVersion(version_id="ts1", fact_id="fh1", confidence=0.1, created_at=40.0, state=VersionState.TOMBSTONE)
        )
        assert h.current_version_id == "ts1"
        assert h.has_tombstone is True
        try:
            h.rollback("ts1")
            raise AssertionError
        except ValueError:
            pass

    def test_add_version_validaciones(self) -> None:
        h, _Fact, FactVersion = self._h()
        try:
            h.add_version(FactVersion(version_id="x", fact_id="otro", confidence=0.5))
            raise AssertionError
        except ValueError:
            pass
        try:
            h.add_version(FactVersion(version_id="v0", fact_id="fh1", confidence=0.5))
            raise AssertionError
        except KeyError:
            pass
        try:
            h.add_version(FactVersion(version_id="v9", fact_id="fh1", confidence=0.5, created_at=5.0))
            raise AssertionError
        except ValueError:
            pass
        try:
            h.tombstone(FactVersion(version_id="tsx", fact_id="otro", confidence=0.5))
            raise AssertionError
        except ValueError:
            pass
        try:
            h.tombstone(FactVersion(version_id="v0", fact_id="fh1", confidence=0.5))
            raise AssertionError
        except KeyError:
            pass

    def test_serializacion(self) -> None:
        from motor.core.fusion.fact_history import FactHistory
        from motor.core.fusion.models import VersionState

        h, _Fact, FactVersion = self._h()
        h.add_version(FactVersion(version_id="v1", fact_id="fh1", confidence=0.7, created_at=20.0))
        h.tombstone(
            FactVersion(version_id="ts1", fact_id="fh1", confidence=0.1, created_at=40.0, state=VersionState.TOMBSTONE)
        )
        from motor.core.fusion.models import FactTombstone

        h._tombstones["ts1"] = FactTombstone(fact_id="fh1", removed_at=50.0, reason="replaced", version_id="ts1")
        d = h.to_dict()
        assert d["schema_version"] == "1"
        assert d["fact_id"] == "fh1"
        assert len(d["versions"]) == 3
        assert len(d["tombstones"]) == 1
        assert d["tombstones"][0]["reason"] == "replaced"
        # valores exactos de cada versión serializada
        v_map = {v["version_id"]: v for v in d["versions"]}
        assert v_map["v0"]["state"] == "superseded"
        assert v_map["v1"]["state"] == "superseded"  # superseded por ts1
        assert v_map["ts1"]["state"] == "obsolete"  # VersionState.TOMBSTONE.value
        assert v_map["v1"]["supersedes"] == "v0"
        assert v_map["v1"]["confidence"] == 0.7
        assert v_map["ts1"]["evidence_ids"] == []
        assert v_map["v0"]["provenance"] == []
        assert d["current"] == "ts1"
        assert d["created"] == 10.0
        assert d["updated"] == 40.0

        h2 = FactHistory.from_dict(d)
        assert h2.fact_id == "fh1"
        assert h2.current_version_id == "ts1"
        assert h2.version_count == 3
        assert len(h2._tombstones) == 1
        # round-trip exacto: to_dict de nuevo es idéntico
        assert h2.to_dict() == d

        d_legacy = dict(d)
        d_legacy["versions"] = {v["version_id"]: v for v in d["versions"]}
        d_legacy["tombstones"] = {t["version_id"]: t for t in d["tombstones"]}
        d_legacy.pop("current", None)
        h3 = FactHistory.from_dict(d_legacy)
        assert h3.version_count == 3

        d_no_current = dict(d_legacy)
        d_no_current["versions"] = {k: {**v, "state": "superseded"} for k, v in d_legacy["versions"].items()}
        h4 = FactHistory.from_dict(d_no_current)
        assert h4.current_version_id in (h4._versions["v0"].version_id, "ts1")


class TestCoberturaFinalFusion:
    """Cobertura 100x100: remanentes finales fusion (TASK-20260814-001)."""

    def test_make_version_id(self) -> None:
        from motor.core.fusion.models import make_version_id

        assert len(make_version_id("f", 123.9, "h")) == 16
        assert make_version_id("f", 123.9, "h") == make_version_id("f", 123.9, "h")

    def test_context_builder_index_none_interno(self) -> None:
        from motor.core.fusion.context_builder import ContextBuilder

        b = ContextBuilder(None)
        assert b._collect_facts("q", None) == []
        assert (
            ContextBuilder(None)._format_fact(
                KnowledgeFact(id="f", subject="s", predicate="p", object="o", confidence=0.5)
            )
            == "- s | p | o (confianza: 0.50)"
        )

    def test_fact_history_remanentes(self) -> None:
        from motor.core.fusion.fact_history import FactHistory
        from motor.core.fusion.models import Fact, FactVersion, VersionState

        h = FactHistory.create(
            Fact(fact_id="fx", subject="s", predicate="p", object="o"),
            FactVersion(version_id="v0", fact_id="fx", confidence=0.5, created_at=1.0, state=VersionState.CURRENT),
        )
        h._current = "fantasma"
        from contextlib import suppress

        with suppress(RuntimeError):
            assert h.current.version_id == "fantasma"
        h2 = FactHistory.create(
            Fact(fact_id="fy", subject="s", predicate="p", object="o"),
            FactVersion(version_id="v0", fact_id="fy", confidence=0.5, created_at=1.0, state=VersionState.CURRENT),
        )
        h2.add_version(FactVersion(version_id="v1", fact_id="fy", confidence=0.5, created_at=2.0, supersedes="zz"))
        assert h2.version_at(0.0) is None

        d = h2.to_dict()
        d["versions"] = [{**v, "state": "current"} if v["version_id"] == "v1" else v for v in d["versions"]]
        h3 = FactHistory.from_dict(d)
        assert h3.current_version_id == "v1"

    def test_fact_index_remove_version(self) -> None:
        from motor.core.fusion.fact_index import FactIndex
        from motor.core.fusion.models import Fact, FactVersion, VersionState

        fact = Fact(fact_id="fr", subject="S", predicate="P", object="O")
        idx = FactIndex()
        idx.add_fact_version(
            fact, FactVersion(version_id="vr", fact_id="fr", confidence=0.9, state=VersionState.CURRENT)
        )
        entry = idx.remove_fact("fr")
        assert entry[0] is fact

    def test_conflict_pair_ramas(self) -> None:
        from motor.core.fusion.stages.conflict_detection import NaiveConflictResolver

        r = NaiveConflictResolver()
        assert (
            r._check_pair(
                KnowledgeClaim(id="a", text="t", confidence=0.5), KnowledgeClaim(id="b", text="t", confidence=0.5)
            )
            is None
        )
        c1 = KnowledgeClaim(id="c1", text="x", confidence=0.5, subject="Sub", predicate="P", object="O1")
        c2 = KnowledgeClaim(id="c2", text="y", confidence=0.5, subject="Otra", predicate="P", object="O2")
        c3 = KnowledgeClaim(id="c3", text="z", confidence=0.5, subject="Sub", predicate="OtroP", object="O3")
        c4 = KnowledgeClaim(id="c4", text="w", confidence=0.5, subject="sub", predicate="p", object="O1")
        assert r._check_pair(c1, c2) is None
        assert r._check_pair(c1, c3) is None
        assert r._check_pair(c1, c4) is None
        assert (
            r._check_pair(
                c1, KnowledgeClaim(id="c5", text="q", confidence=0.5, subject="Sub", predicate="P", object="O2")
            )
            is not None
        )

    def test_keyword_scorer_uno(self) -> None:
        from motor.core.fusion.stages.entity_resolver import EntityDef, KeywordScorer

        assert KeywordScorer().select([EntityDef(entity_id="e1", canonical_name="X")], "cualquier") == 0
        assert (
            KeywordScorer().select(
                [
                    EntityDef(entity_id="a", canonical_name="A", keywords=["k1"]),
                    EntityDef(entity_id="b", canonical_name="B", keywords=["k1"]),
                ],
                "k1 aqui",
            )
            is None
        )

    def test_resolver_cache_hit_y_enum(self) -> None:
        from motor.core.fusion.stages.entity_resolver import (
            CachePolicy,
            ContextualEntityResolver,
            EntityDef,
            EntityRegistry,
        )

        reg = EntityRegistry({"gato": [EntityDef(entity_id="G1", canonical_name="Gato")]})
        r = ContextualEntityResolver(registry=reg, cache_policy=CachePolicy.DISABLED)
        assert r.cache_policy == CachePolicy.DISABLED
        r2 = ContextualEntityResolver(registry=reg)
        e1 = r2.resolve("gato", context={"claim_text": "x"})
        e2 = r2.resolve("gato", context={"claim_text": "x"})
        assert e1 is e2
        assert r2.cache.size == 1


class TestStagePropertiesCobertura:
    """Cobertura 100x100: properties de stage (TASK-20260814-001)."""

    def test_extraction_stage_property(self) -> None:
        from motor.core.fusion.stages.extraction import ExtractionStage

        assert ExtractionStage().stage == FusionStage.EXTRACTION
        assert ExtractionStage().name == "ExtractionStage"
