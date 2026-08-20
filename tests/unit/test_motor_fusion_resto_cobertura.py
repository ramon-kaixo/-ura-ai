"""Cobertura 100x100 de motor/core/fusion (6 modulos). TASK-20260820-013."""

from __future__ import annotations

import time
from dataclasses import dataclass

import pytest

import motor.core.fusion.engine as engine_mod
from motor.core.fusion.base import (
    BaseStage,
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
from motor.core.fusion.engine import FusionPipeline, FusionStage, build_default_pipeline
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
from motor.core.fusion.stages.normalization import NormalizationStage
from motor.core.fusion.stages.source_scorer import QualitySourceScorer, SourceScoringStage

# ── models: helpers ──────────────────────────────────────────


def test_normalize_identity() -> None:
    assert normalize_identity("  El   Sistema  ") == "el sistema"
    assert normalize_identity("¡Hola, mundo!") == "hola mundo"
    assert normalize_identity("  ") == ""


def test_make_claim_id_determinista() -> None:
    a = make_claim_id("e1", "El gato")
    b = make_claim_id("e1", "el gato")
    assert a == b
    assert len(a) == 16


def test_make_fact_id_normaliza() -> None:
    a = make_fact_id("Apple ", "es", "fruta")
    b = make_fact_id("apple", "es", "fruta")
    assert a == b


def test_make_version_id() -> None:
    a = make_version_id("f1", 100.5, "hash")
    b = make_version_id("f1", 100.9, "hash")  # int() ignora decimales
    assert a == b
    assert len(a) == 16


def test_make_conflict_id() -> None:
    a = make_conflict_id("c1", "c2", "contradiction")
    assert len(a) == 16
    assert a != make_conflict_id("c2", "c1", "contradiction")


def test_conflict_type_valores() -> None:
    assert ConflictType.CONTRADICTION.value == "contradiction"
    assert ConflictType.OPINION.value == "opinion"


def test_resolution_status_valores() -> None:
    assert ResolutionStatus.UNKNOWN.value == "unknown"
    assert ResolutionStatus.ERROR.value == "error"


def test_version_state_valores() -> None:
    assert VersionState.CURRENT.value == "current"
    assert VersionState.TOMBSTONE.value == "obsolete"


def test_fact_frozen() -> None:
    f = Fact(fact_id="f1", subject="s", predicate="p", object="o")
    assert f.fact_id == "f1"
    with pytest.raises(Exception):
        f.subject = "cambiar"  # type: ignore[misc]


def test_fact_tombstone() -> None:
    t = FactTombstone(fact_id="f1", removed_at=1.0, reason="old")
    assert t.version_id is None


def test_fact_version_defaults() -> None:
    v = FactVersion(version_id="v1", fact_id="f1", confidence=0.9)
    assert v.evidence_ids == ()
    assert v.state == VersionState.CURRENT
    assert v.supersedes is None


def test_resolved_entity_defaults() -> None:
    r = ResolvedEntity(entity_id="E1", canonical_name="Apple", confidence=0.9)
    assert r.status == ResolutionStatus.RESOLVED
    assert r.aliases == ()


def test_source_score_defaults() -> None:
    s = SourceScore(url="http://x")
    assert s.authority == 0.0
    assert s.overall == 0.0


def test_knowledge_claim_defaults() -> None:
    c = KnowledgeClaim(id="c1", text="texto", confidence=0.5)
    assert c.created_at > 0
    assert c.normalized_text == ""
    assert c.evidence is None


def test_conflict_defaults() -> None:
    c = Conflict(id="x", claim_a="a", claim_b="b")
    assert c.conflict_type == ConflictType.CONTRADICTION
    assert c.resolved is False


def test_conflict_graph() -> None:
    g = ConflictGraph(
        edges=[Conflict(id="1", claim_a="a", claim_b="b"), Conflict(id="2", claim_a="b", claim_b="c", resolved=True)],
        claim_ids={"a", "b", "c"},
    )
    assert g.has_conflicts is True
    assert g.unresolved_count == 1
    assert len(g.unresolved) == 1
    assert set(g.claims_for("b")) == {"a", "c"}
    assert set(g.claims_for("a")) == {"b"}


def test_conflict_graph_clusters() -> None:
    g = ConflictGraph(
        edges=[
            Conflict(id="1", claim_a="a", claim_b="b"),
            Conflict(id="2", claim_a="b", claim_b="c"),
            Conflict(id="3", claim_a="x", claim_b="y"),
        ],
        claim_ids={"a", "b", "c", "x", "y"},
    )
    clusters = g.clusters()
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [2, 3]


def test_conflict_graph_from_edges() -> None:
    edges = [Conflict(id="1", claim_a="a", claim_b="b")]
    g = ConflictGraph.from_edges(edges)
    assert g.claim_ids == {"a", "b"}
    assert g.edges == edges


def test_conflict_graph_clusters_con_nodo_aislado() -> None:
    g = ConflictGraph(edges=[Conflict(id="1", claim_a="a", claim_b="b")], claim_ids={"a", "b", "solo"})
    clusters = g.clusters()
    assert sorted(len(c) for c in clusters) == [1, 2]  # nodo aislado → componente propia


def test_conflict_graph_sin_conflictos() -> None:
    g = ConflictGraph()
    assert g.has_conflicts is False
    assert g.unresolved_count == 0
    assert g.clusters() == []


def test_knowledge_fact_frozen() -> None:
    kf = KnowledgeFact(id="f1", subject="s", predicate="p", object="o", confidence=0.5)
    assert kf.version == 1
    assert kf.superseded_by is None


def test_knowledge_delta() -> None:
    d = KnowledgeDelta()
    assert d.has_changes is False
    d2 = KnowledgeDelta(facts_added=(KnowledgeFact(id="f", subject="s", predicate="p", object="o", confidence=0.5),))
    assert d2.has_changes is True


def test_evidence_set_len() -> None:
    es = EvidenceSet(claims=[KnowledgeClaim(id="c", text="t", confidence=0.5)])
    assert len(es) == 1


def test_fusion_provenance_defaults() -> None:
    p = FusionProvenance()
    assert p.pipeline_version == ""


def test_stage_provenance_defaults() -> None:
    sp = StageProvenance(stage_name="n", stage_version="v", transformer="t")
    assert sp.timestamp > 0


def test_fusion_context_defaults() -> None:
    ctx = FusionContext()
    assert ctx.claims == []
    assert ctx.transforms == []
    assert ctx.bundle is None


def test_fusion_result_defaults() -> None:
    r = FusionResult()
    assert r.accepted == ()
    assert r.index is None


# ── bridge ───────────────────────────────────────────────────


def _kf() -> KnowledgeFact:
    return KnowledgeFact(
        id="kf1",
        subject="alice",
        predicate="tiene",
        object="gato",
        confidence=0.8,
        evidence_ids=("e1", "e2"),
        provenance=("p1",),
        version=3,
        created_at=100.0,
    )


def test_knowledge_fact_to_semantic() -> None:
    d = knowledge_fact_to_semantic_fact(_kf())
    assert d["subject"] == "alice"
    assert d["object_value"] == "gato"
    assert d["confidence"] == 0.8
    assert d["importance"] == pytest.approx(0.64)
    assert d["source_episode_ids"] == ["e1", "e2"]
    assert d["tags"] == ["fusion", "knowledge"]
    assert d["version"] == 3
    assert d["created_at"] == 100.0
    assert d["metadata"]["origin"] == "fusion_pipeline"
    assert d["metadata"]["provenance"] == ["p1"]


def test_knowledge_fact_created_at_cero() -> None:
    kf = KnowledgeFact(id="x", subject="s", predicate="p", object="o", confidence=0.5, created_at=0.0)
    d = knowledge_fact_to_semantic_fact(kf)
    assert d["created_at"] == 0.0


def test_fact_version_to_semantic() -> None:
    fact = Fact(fact_id="f1", subject="bob", predicate="dice", object="hola")
    version = FactVersion(
        version_id="v2",
        fact_id="f1",
        confidence=0.9,
        evidence_ids=("e9",),
        provenance=("pp",),
        created_at=200.0,
        supersedes="v1",
    )
    d = fact_version_to_semantic_fact(fact, version)
    assert d["id"] == "f1"
    assert d["subject"] == "bob"
    assert d["confidence"] == 0.9
    assert d["importance"] == pytest.approx(0.72)
    assert d["source_episode_ids"] == ["e9"]
    assert d["tags"] == ["fusion", "versioned"]
    assert d["version"] == 1
    assert d["created_at"] == 200.0
    assert d["metadata"]["version_id"] == "v2"
    assert d["metadata"]["supersedes"] == "v1"


# ── normalization stage ──────────────────────────────────────


def _claim(cid: str, text: str) -> KnowledgeClaim:
    return KnowledgeClaim(id=cid, text=text, confidence=0.5)


def test_normalization_stage_props() -> None:
    s = NormalizationStage()
    assert s.stage == FusionStage.NORMALIZATION
    assert s.name == "NormalizationStage"
    assert s.version == "1.0.0"


def test_normalization_stage_ejecuta() -> None:
    s = NormalizationStage()
    ctx = FusionContext(claims=[_claim("c1", "  El   Gato "), _claim("c2", "Hola,  Mundo!")])
    out = s.execute(ctx)
    assert out.claims[0].normalized_text == "el gato"
    assert out.claims[1].normalized_text == "hola mundo"
    assert out.statistics["claims_normalized"] == 2
    assert len(out.transforms) == 1
    assert out.transforms[0].stage_name == "NormalizationStage"


def test_normalization_metodo() -> None:
    assert NormalizationStage._normalize("  HOLA   MUNDO,  ") == "hola mundo"
    assert NormalizationStage._normalize("café  con leche!") == "café con leche"


# ── source scorer ────────────────────────────────────────────


def _claim_con_evidencia(url: str, fetched_at: float) -> KnowledgeClaim:
    @dataclass
    class _Ev:
        document_url: str
        fetched_at: float

    c = KnowledgeClaim(id="c1", text="t", confidence=0.5)
    c.evidence = _Ev(document_url=url, fetched_at=fetched_at)  # type: ignore[assignment]
    return c


def test_quality_source_scorer_tlds() -> None:
    scorer = QualitySourceScorer()
    assert scorer._score_authority("https://www.gob.gob") == 0.5  # tld "gob" no mapeado
    assert scorer._score_authority("https://gob.es") == 0.5  # tld "es" no mapeado
    assert scorer._score_authority("https://example.edu") == 0.8
    assert scorer._score_authority("https://example.org") == 0.6
    assert scorer._score_authority("https://com") == 0.5  # sin punto → unknown


def test_quality_source_scorer_parse_tld() -> None:
    assert QualitySourceScorer._parse_tld("https://www.example.gov/path") == "gov"
    assert QualitySourceScorer._parse_tld("sin-url") == "unknown"


def test_quality_source_scorer_freshness() -> None:
    assert QualitySourceScorer._score_freshness(time.time()) == pytest.approx(1.0)
    viejo = time.time() - 365 * 86400
    assert QualitySourceScorer._score_freshness(viejo) == pytest.approx(0.1)


def test_quality_source_scorer_score() -> None:
    scorer = QualitySourceScorer()
    c = _claim_con_evidencia("https://www.example.edu/doc", time.time())
    s = scorer.score(c)
    assert s.url == "https://www.example.edu/doc"
    assert s.authority == 0.8
    assert s.freshness == pytest.approx(1.0)
    assert s.overall == pytest.approx(0.9)


def test_quality_source_scorer_sin_evidencia() -> None:
    scorer = QualitySourceScorer()
    c = KnowledgeClaim(id="c", text="t", confidence=0.5)
    s = scorer.score(c)
    assert s.url == "unknown"
    assert s.authority == 0.5


def test_quality_source_scorer_score_evidence() -> None:
    scorer = QualitySourceScorer()
    es = EvidenceSet(
        claims=[
            _claim_con_evidencia("https://www.example.edu/doc", time.time()),
            _claim_con_evidencia("https://www.gov.xx/doc", time.time()),
        ]
    )
    scores = scorer.score_evidence(es)
    assert len(scores) == 2
    assert scores[0].authority == 0.8


def test_source_scoring_stage() -> None:
    s = SourceScoringStage()
    assert s.stage == FusionStage.SOURCE_SCORING
    assert s.name == "SourceScoringStage"
    assert s.version == "1.0.0"
    ctx = FusionContext(claims=[_claim_con_evidencia("https://www.example.edu/doc", time.time())])
    out = s.execute(ctx)
    assert out.claims[0].source_score is not None
    assert out.statistics["claims_scored"] == 1
    assert out.provenance.source_scorer_name == "QualitySourceScorer"
    assert out.provenance.source_scorer_version == "1.0.0"


def test_source_scoring_stage_con_scorer() -> None:
    class _ScorerStub(SourceScorer):
        def score(self, claim: KnowledgeClaim) -> SourceScore:
            return SourceScore(url="u", authority=0.5, freshness=0.5, overall=0.5)

        def score_evidence(self, evidence_set: EvidenceSet) -> list[SourceScore]:
            return [self.score(c) for c in evidence_set.claims]

    s = SourceScoringStage(scorer=_ScorerStub())
    ctx = FusionContext(claims=[_claim("c", "t")])
    out = s.execute(ctx)
    assert out.claims[0].source_score.overall == 0.5


# ── engine: pipeline ─────────────────────────────────────────


def test_fusion_stage_valores() -> None:
    assert FusionStage.EXTRACTION.value == "extraction"
    assert FusionStage.SELECTION.value == "selection"


def test_build_default_pipeline() -> None:
    stages = build_default_pipeline()
    assert len(stages) == 7
    assert stages[0].stage == FusionStage.NORMALIZATION
    assert stages[-1].stage == FusionStage.SELECTION


def test_fusion_pipeline_default() -> None:
    p = FusionPipeline.default()
    assert len(p.stages) == 7
    assert p.engine is None


def test_fusion_pipeline_stages_prop() -> None:
    p = FusionPipeline(stages=[NormalizationStage()])
    assert len(p.stages) == 1
    assert p.stage_times == {}
    assert p.engine is None


def test_fusion_pipeline_register_stage() -> None:
    p = FusionPipeline()
    s1 = NormalizationStage()
    s2 = SourceScoringStage()
    p.register_stage(s1)
    p.register_stage(s2, index=0)
    assert p.stages == [s2, s1]


def test_fusion_pipeline_run_con_engine() -> None:
    class _EngineStub(FusionEngine):
        def fuse(self, bundle, documents):
            return FusionResult()

    p = FusionPipeline(engine=_EngineStub())
    r = p.run(None, [])
    assert isinstance(r, FusionResult)


def test_fusion_pipeline_run_sin_etapas() -> None:
    p = FusionPipeline()
    r = p.run(None, [])
    assert r.index is not None  # FactIndex vacío construido
    assert r.accepted == ()


def test_fusion_pipeline_run_con_etapas() -> None:
    p = FusionPipeline(stages=[NormalizationStage()])
    bundle = type("B", (), {})()
    r = p.run(bundle, [])
    assert r.statistics == {"claims_normalized": 0}
    assert isinstance(r, FusionResult)


def test_build_context_y_result() -> None:
    ctx = engine_mod._build_context(None, [])
    assert isinstance(ctx, FusionContext)
    res = engine_mod._context_to_result(ctx)
    assert isinstance(res, FusionResult)
    assert res.accepted == ()


def test_fusion_pipeline_run_con_facts_index() -> None:
    class _EtapaFacts:
        stage = FusionStage.MERGE

        def execute(self, context: FusionContext) -> FusionContext:
            context.facts.append(
                KnowledgeFact(
                    id="kf1",
                    subject="alice",
                    predicate="tiene",
                    object="gato",
                    confidence=0.8,
                    evidence_ids=("e1",),
                    provenance=("p1",),
                    version=2,
                    created_at=100.0,
                )
            )
            return context

    p = FusionPipeline(stages=[_EtapaFacts()])
    r = p.run(None, [])
    assert len(r.accepted) == 1
    assert r.index is not None
    assert r.accepted[0].subject == "alice"


# ── base: contratos abstractos ───────────────────────────────


def test_base_stage_execute_registra_transform() -> None:
    class _Etapa(BaseStage):
        @property
        def stage(self) -> FusionStage:
            return FusionStage.NORMALIZATION

        @property
        def name(self) -> str:
            return "TestStage"

        @property
        def version(self) -> str:
            return "0.1"

        def _execute(self, context: FusionContext) -> FusionContext:
            context.statistics["touched"] = True
            return context

    ctx = FusionContext()
    out = _Etapa().execute(ctx)
    assert out.transforms[0].stage_name == "TestStage"
    assert out.transforms[0].input_claims == 0


def test_base_stage_execute_con_stats() -> None:
    class _EtapaStats(BaseStage):
        @property
        def stage(self) -> FusionStage:
            return FusionStage.MERGE

        @property
        def name(self) -> str:
            return "StatsStage"

        @property
        def version(self) -> str:
            return "0.2"

        def _record_stats(self) -> None:
            pass

        def _execute(self, context: FusionContext) -> FusionContext:
            context.facts.append(KnowledgeFact(id="f", subject="s", predicate="p", object="o", confidence=0.5))
            return context

    ctx = FusionContext()
    out = _EtapaStats().execute(ctx)
    assert "StatsStage" in out.statistics["stages"]
    assert out.statistics["stages"]["StatsStage"]["output_facts"] == 1


def test_pipeline_stage_deterministic_default() -> None:
    class _Etapa(PipelineStage):
        @property
        def stage(self) -> FusionStage:
            return FusionStage.EXTRACTION

        @property
        def name(self) -> str:
            return "X"

        @property
        def version(self) -> str:
            return "1"

        def execute(self, context: FusionContext) -> FusionContext:
            return context

    assert _Etapa().deterministic is True


def test_abstractos_lanzan() -> None:
    with pytest.raises(TypeError):
        FusionEngine()
    with pytest.raises(TypeError):
        ConflictResolver()
    with pytest.raises(TypeError):
        SourceScorer()
    with pytest.raises(TypeError):
        EntityResolver()
    with pytest.raises(TypeError):
        PipelineStage()
    with pytest.raises(TypeError):
        KnowledgeMerger()
    with pytest.raises(TypeError):
        ChangeDetector()
    with pytest.raises(TypeError):
        MemoryCandidateSelector()


def test_conflict_resolver_version_default() -> None:
    class _Resolver(ConflictResolver):
        def detect(self, claims):
            return []

        def resolve(self, conflicts, claims):
            return [], []

    assert _Resolver().version == "naive"
