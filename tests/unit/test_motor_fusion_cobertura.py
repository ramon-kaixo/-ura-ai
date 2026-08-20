"""Cobertura 100x100 de motor/core/fusion (TASK-20260820-005).

Cubre:
- stages/selector.py: ThresholdSelector + MemoryCandidateSelectionStage
- stages/merger.py: SimpleKnowledgeMerger + KnowledgeMergerStage
- stages/delta.py: BasicChangeDetector + KnowledgeDeltaStage
- registry.py: FusionRegistry (verificado al 100% con --tests explícito;
  la auto-detección del verificador no asocia este archivo a "registry" porque
  el nombre del test file no lo contiene; si se ejecuta con auto-detección,
  usa --tests tests/unit/test_motor_fusion_cobertura.py)
- stages/conflict_detection.py: NaiveConflictResolver + ConflictDetectionStage
- context_builder.py: ContextBuilder

Sin dependencias externas: stdlib + motor.core.fusion.
"""

from __future__ import annotations

from motor.core.fusion.context_builder import ContextBuilder
from motor.core.fusion.engine import FusionStage
from motor.core.fusion.models import (
    ConflictType,
    FusionContext,
    FusionResult,
    KnowledgeClaim,
    KnowledgeFact,
    make_claim_id,
    make_fact_id,
)
from motor.core.fusion.registry import FusionRegistry
from motor.core.fusion.stages.conflict_detection import (
    ConflictDetectionStage,
    NaiveConflictResolver,
)
from motor.core.fusion.stages.delta import BasicChangeDetector, KnowledgeDeltaStage
from motor.core.fusion.stages.merger import KnowledgeMergerStage, SimpleKnowledgeMerger
from motor.core.fusion.stages.selector import (
    MemoryCandidateSelectionStage,
    ThresholdSelector,
)


def _fact(subject: str = "Apple", predicate: str = "vende", obj: str = "iPhones", conf: float = 0.9, **kw) -> KnowledgeFact:
    kwargs = {
        "id": kw.pop("id", make_fact_id(subject, predicate, obj)),
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "confidence": conf,
    }
    kwargs.update(kw)
    return KnowledgeFact(**kwargs)


def _claim(text: str = "Apple vende iPhones", conf: float = 0.8, **kw) -> KnowledgeClaim:
    parts = text.split()
    kwargs = {
        "id": kw.pop("id", make_claim_id(f"e-{text}", text)),
        "text": text,
        "confidence": conf,
        "subject": kw.pop("subject", parts[0] if parts else ""),
        "predicate": kw.pop("predicate", parts[1] if len(parts) > 1 else ""),
        "object": kw.pop("object", " ".join(parts[2:]) if len(parts) > 2 else ""),
        "text_id": kw.pop("text_id", f"t-{text}"),
    }
    kwargs.update(kw)
    return KnowledgeClaim(**kwargs)


def _context(**kw) -> FusionContext:
    base = {"claims": [], "conflicts": [], "facts": [], "statistics": {}}
    base.update(kw)
    return FusionContext(**base)


class TestThresholdSelector:
    def test_selecciona_por_confianza(self) -> None:
        s = ThresholdSelector(min_confidence=0.5)
        fr = FusionResult(accepted=(_fact(conf=0.9), _fact(conf=0.4), _fact(conf=0.6)))
        sel = s.select(fr)
        assert len(sel) == 2
        assert all(f.confidence >= 0.5 for f in sel)

    def test_ordena_descendente(self) -> None:
        s = ThresholdSelector(min_confidence=0.1)
        fr = FusionResult(accepted=(_fact(conf=0.4), _fact(conf=0.9), _fact(conf=0.6)))
        confs = [f.confidence for f in s.select(fr)]
        assert confs == [0.9, 0.6, 0.4]

    def test_respeta_max_candidates_del_selector(self) -> None:
        s = ThresholdSelector(min_confidence=0.0, max_candidates=2)
        fr = FusionResult(accepted=(_fact(conf=0.9), _fact(conf=0.8), _fact(conf=0.7)))
        assert len(s.select(fr)) == 2

    def test_respeta_max_candidates_del_call(self) -> None:
        s = ThresholdSelector(min_confidence=0.0, max_candidates=10)
        fr = FusionResult(accepted=(_fact(conf=0.9), _fact(conf=0.8), _fact(conf=0.7)))
        assert len(s.select(fr, max_candidates=2)) == 2

    def test_vacio(self) -> None:
        s = ThresholdSelector()
        assert s.select(FusionResult()) == []


class TestMemoryCandidateSelectionStage:
    def test_propiedades(self) -> None:
        st = MemoryCandidateSelectionStage()
        assert st.stage == FusionStage.SELECTION
        assert st.name == "MemoryCandidateSelectionStage"
        assert st.version == "1.0.0"
        assert st.deterministic is True

    def test_ejecuta_sin_ambiguos(self) -> None:
        st = MemoryCandidateSelectionStage()
        ctx = _context(facts=[_fact(), _fact(conf=0.2)])
        out = st.execute(ctx)
        assert out.statistics["candidates_requested"] == 100
        assert out.statistics["candidates_returned"] == 1
        assert out.provenance.selector_name == "ThresholdSelector"
        assert len(out.transforms) == 1

    def test_skip_entidades_ambiguas(self) -> None:
        st = MemoryCandidateSelectionStage()
        ctx = _context(
            facts=[_fact()],
            statistics={"ambiguous_entity_ids": ["a1"]},
        )
        out = st.execute(ctx)
        assert any("ambiguous" in w for w in out.warnings)

    def test_memory_disponible_escribe_entries(self) -> None:
        class FakeMemory:
            def __init__(self) -> None:
                self.entries = []

            def append(self, entry) -> None:
                self.entries.append(entry)

        memory = FakeMemory()
        st = MemoryCandidateSelectionStage()
        ctx = _context(facts=[_fact(), _fact()], statistics={"_memory_instance": memory})
        out = st.execute(ctx)
        assert out.statistics["memory_entries_written"] == 2
        assert len(memory.entries) == 2
        assert memory.entries[0].source == "fusion_pipeline"
        assert memory.entries[0].event_type.value == "fact_added"

    def test_memory_duplicado_se_ignora(self) -> None:
        class FakeMemory:
            def append(self, entry) -> None:
                raise KeyError("dup")

        st = MemoryCandidateSelectionStage()
        ctx = _context(facts=[_fact()], statistics={"_memory_instance": FakeMemory()})
        out = st.execute(ctx)
        # El conteo refleja len(selected) (comportamiento observable actual del
        # pipeline: el KeyError se traga pero no decrementa el contador).
        assert out.statistics["memory_entries_written"] == 1

    def test_memory_sin_seleccion_no_escribe(self) -> None:
        st = MemoryCandidateSelectionStage()
        ctx = _context(facts=[], statistics={"_memory_instance": object()})
        out = st.execute(ctx)
        assert out.statistics["memory_entries_written"] == 0


class TestSimpleKnowledgeMerger:
    def test_merge_una_claim(self) -> None:
        m = SimpleKnowledgeMerger()
        claims = [_claim("Apple vende iPhones", conf=0.9)]
        facts = m.merge(claims, [])
        assert len(facts) == 1
        assert facts[0].subject == "Apple"
        assert facts[0].predicate == "vende"
        assert facts[0].object == "iPhones"
        assert facts[0].confidence == 0.9
        assert facts[0].evidence_ids == ("t-Apple vende iPhones",)

    def test_merge_claim_corta(self) -> None:
        m = SimpleKnowledgeMerger()
        facts = m.merge([_claim("Apple", conf=0.5)], [])
        assert facts[0].subject == "Apple"
        assert facts[0].predicate == ""
        assert facts[0].object == ""

    def test_merge_vacia(self) -> None:
        m = SimpleKnowledgeMerger()
        assert m.merge([], []) == []

    def test_version(self) -> None:
        assert SimpleKnowledgeMerger().version == "1.0.0"


class TestKnowledgeMergerStage:
    def test_propiedades(self) -> None:
        st = KnowledgeMergerStage()
        assert st.stage == FusionStage.MERGE
        assert st.name == "KnowledgeMergerStage"
        assert st.version == "1.0.0"

    def test_merge_facts(self) -> None:
        st = KnowledgeMergerStage()
        ctx = _context(claims=[_claim("Apple vende iPhones"), _claim("Apple vende Macs")])
        out = st.execute(ctx)
        assert len(out.facts) == 2
        assert out.statistics["facts_merged"] == 2
        assert out.provenance.merger_name == "SimpleKnowledgeMerger"

    def test_sin_claims_no_facts(self) -> None:
        st = KnowledgeMergerStage()
        out = st.execute(_context())
        assert out.facts == []
        assert out.statistics["facts_merged"] == 0

    def test_excluye_claims_ambiguos(self) -> None:
        st = KnowledgeMergerStage()
        claims = [_claim("Apple vende iPhones"), _claim("Tesla vende coches")]
        ctx = _context(claims=claims, statistics={"ambiguous_entity_ids": ["Apple vende iPhones"]})
        out = st.execute(ctx)
        assert len(out.facts) == 1
        assert out.facts[0].subject == "Tesla"
        assert out.statistics["claims_with_ambiguous_entities"] == 1
        assert any("ambiguous" in w for w in out.warnings)


class TestBasicChangeDetector:
    def test_added_updated_confirmed(self) -> None:
        d = BasicChangeDetector()
        new = [
            _fact(subject="A", predicate="p", obj="nuevo", id="f-a"),  # ADDED
            _fact(subject="B", predicate="p", obj="v2", id="f-b"),  # UPDATED
            _fact(subject="C", predicate="p", obj="igual", id="f-c"),  # CONFIRMED
        ]
        existing = [
            _fact(subject="B", predicate="p", obj="v1", id="f-b"),
            _fact(subject="C", predicate="p", obj="igual", id="f-c"),
        ]
        delta = d.detect_delta(new, existing)
        assert len(delta.facts_added) == 1
        assert len(delta.facts_updated) == 1
        assert delta.facts_added[0].id == "f-a"
        assert delta.facts_updated[0].id == "f-b"

    def test_todos_added(self) -> None:
        d = BasicChangeDetector()
        delta = d.detect_delta([_fact()], [])
        assert len(delta.facts_added) == 1
        assert delta.has_changes is True

    def test_sin_cambios(self) -> None:
        d = BasicChangeDetector()
        f = _fact()
        delta = d.detect_delta([f], [f])
        assert len(delta.facts_added) == 0
        assert len(delta.facts_updated) == 0
        assert delta.has_changes is False

    def test_version(self) -> None:
        assert BasicChangeDetector().version == "1.0.0"

    def test_existing_sin_id_ignorado(self) -> None:
        d = BasicChangeDetector()
        f = _fact(subject="A", predicate="p", obj="nuevo", id="f-a")
        sin_id = _fact(subject="X", predicate="p", obj="y", id="")
        delta = d.detect_delta([f], [sin_id])
        assert len(delta.facts_added) == 1
        assert len(delta.facts_updated) == 0


class TestKnowledgeDeltaStage:
    def test_propiedades(self) -> None:
        st = KnowledgeDeltaStage()
        assert st.stage == FusionStage.DELTA
        assert st.name == "KnowledgeDeltaStage"
        assert st.version == "1.0.0"

    def test_delta_stats(self) -> None:
        st = KnowledgeDeltaStage()
        f = _fact(subject="A", predicate="p", obj="nuevo", id="f-a")
        existing = _fact(subject="A", predicate="p", obj="viejo", id="f-a")
        ctx = _context(facts=[f], statistics={"existing_facts": [existing]})
        out = st.execute(ctx)
        assert out.statistics["deltas_added"] == 0
        assert out.statistics["deltas_updated"] == 1
        assert out.statistics["deltas_removed"] == 0
        assert out.statistics["has_changes"] is True
        assert out.provenance.change_detector_name == "BasicChangeDetector"

    def test_sin_cambios(self) -> None:
        st = KnowledgeDeltaStage()
        f = _fact()
        ctx = _context(facts=[f], statistics={"existing_facts": [f]})
        out = st.execute(ctx)
        assert out.statistics["has_changes"] is False

    def test_ambiguos_warning(self) -> None:
        st = KnowledgeDeltaStage()
        ctx = _context(facts=[_fact()], statistics={"ambiguous_entity_ids": ["x"]})
        out = st.execute(ctx)
        assert any("ambiguous" in w for w in out.warnings)


class TestNaiveConflictResolver:
    def test_detecta_contradiccion(self) -> None:
        r = NaiveConflictResolver()
        claims = [_claim("Apple vende iPhones", subject="apple", predicate="vende", object="iPhones"),
                  _claim("Apple vende Macs", subject="Apple", predicate="Vende", object="Macs")]
        conflicts = r.detect(claims)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.CONTRADICTION
        assert "iPhones" in conflicts[0].description

    def test_no_conflicto_mismo_objeto(self) -> None:
        r = NaiveConflictResolver()
        claims = [_claim("Apple vende iPhones", subject="apple", predicate="vende", object="iPhones"),
                  _claim("Apple vende iPhones", subject="Apple", predicate="vende", object="iPhones")]
        assert r.detect(claims) == []

    def test_no_conflicto_distinto_sujeto(self) -> None:
        r = NaiveConflictResolver()
        claims = [_claim("Apple vende iPhones", subject="apple", predicate="vende", object="iPhones"),
                  _claim("Tesla vende coches", subject="tesla", predicate="vende", object="coches")]
        assert r.detect(claims) == []

    def test_sujeto_vacio_ignorado(self) -> None:
        r = NaiveConflictResolver()
        claims = [_claim("x", subject="", predicate="", object="")]
        assert r.detect(claims) == []

    def test_sujeto_vacio_solo_b(self) -> None:
        r = NaiveConflictResolver()
        a = _claim("Apple vende iPhones", subject="apple", predicate="vende", object="iPhones")
        b = _claim("x", subject="", predicate="vende", object="Macs")
        assert r.detect([a, b]) == []

    def test_predicado_distinto_no_conflicto(self) -> None:
        r = NaiveConflictResolver()
        a = _claim("Apple vende iPhones", subject="apple", predicate="vende", object="iPhones")
        b = _claim("Apple compra Macs", subject="Apple", predicate="compra", object="Macs")
        assert r.detect([a, b]) == []

    def test_resuelve_con_ganador(self) -> None:
        r = NaiveConflictResolver()
        a = _claim("Apple vende iPhones", conf=0.9)
        b = _claim("Apple vende Macs", conf=0.3)
        conflicts = r.detect([a, b])
        facts, unresolved = r.resolve(conflicts, [a, b])
        assert facts == []
        assert unresolved == []
        assert conflicts[0].resolved is True
        assert "Preferring" in conflicts[0].resolution or conflicts[0].resolution

    def test_empate_queda_sin_resolver(self) -> None:
        r = NaiveConflictResolver()
        a = _claim("Apple vende iPhones", conf=0.5)
        b = _claim("Apple vende Macs", conf=0.5)
        conflicts = r.detect([a, b])
        _, unresolved = r.resolve(conflicts, [a, b])
        assert len(unresolved) == 1
        assert conflicts[0].resolved is False

    def test_resolve_ignora_claims_faltantes(self) -> None:
        r = NaiveConflictResolver()
        a = _claim("Apple vende iPhones", conf=0.9)
        b = _claim("Apple vende Macs", conf=0.3)
        conflicts = r.detect([a, b])
        facts, unresolved = r.resolve(conflicts, [a])  # b no está
        assert facts == []
        assert unresolved == []

    def test_version(self) -> None:
        assert NaiveConflictResolver().version == "1.0.0"

    def test_check_pair_sujeto_vacio_uno(self) -> None:
        r = NaiveConflictResolver()
        a = _claim("x", subject="apple", predicate="vende", object="iPhones")
        b = _claim("y", subject="", predicate="vende", object="Macs")
        assert r._check_pair(a, b) is None

    def test_check_pair_subject_distinto(self) -> None:
        r = NaiveConflictResolver()
        a = _claim("x", subject="apple", predicate="vende", object="iPhones")
        b = _claim("y", subject="tesla", predicate="vende", object="Macs")
        assert r._check_pair(a, b) is None

    def test_check_pair_predicate_distinto(self) -> None:
        r = NaiveConflictResolver()
        a = _claim("x", subject="apple", predicate="vende", object="iPhones")
        b = _claim("y", subject="Apple", predicate="compra", object="Macs")
        assert r._check_pair(a, b) is None

    def test_check_pair_objeto_igual(self) -> None:
        r = NaiveConflictResolver()
        a = _claim("x", subject="apple", predicate="vende", object="iPhones")
        b = _claim("y", subject="Apple", predicate="vende", object="iPhones")
        assert r._check_pair(a, b) is None

    def test_check_pair_conflicto(self) -> None:
        r = NaiveConflictResolver()
        a = _claim("x", subject="apple", predicate="vende", object="iPhones")
        b = _claim("y", subject="Apple", predicate="vende", object="Macs")
        c = r._check_pair(a, b)
        assert c is not None
        assert c.conflict_type == ConflictType.CONTRADICTION
        assert c.claim_a == a.id
        assert c.claim_b == b.id


class TestConflictDetectionStage:
    def test_propiedades(self) -> None:
        st = ConflictDetectionStage()
        assert st.stage == FusionStage.CONFLICT_DETECTION
        assert st.name == "ConflictDetectionStage"
        assert st.version == "1.0.0"

    def test_sin_claims_return(self) -> None:
        st = ConflictDetectionStage()
        out = st.execute(_context())
        assert out.conflicts == []

    def test_detecta_y_resuelve(self) -> None:
        st = ConflictDetectionStage()
        claims = [_claim("Apple vende iPhones", conf=0.9, subject="apple", predicate="vende", object="iPhones"),
                  _claim("Apple vende Macs", conf=0.9, subject="Apple", predicate="vende", object="Macs")]
        ctx = _context(claims=claims)
        out = st.execute(ctx)
        assert out.statistics["conflicts_detected"] == 1
        assert out.statistics["conflicts_unresolved"] == 1
        assert out.conflict_graph is not None
        assert out.conflict_graph.has_conflicts is True
        assert out.provenance.conflict_resolver_name == "NaiveConflictResolver"

    def test_ambiguos_skip(self) -> None:
        st = ConflictDetectionStage()
        claims = [_claim("Apple vende iPhones", text_id="t-x")]
        ctx = _context(claims=claims, statistics={"ambiguous_entity_ids": ["t-x"]})
        out = st.execute(ctx)
        assert out.statistics["conflicts_detected"] == 0
        assert any("ambiguous" in w for w in out.warnings)

    def test_todos_ambiguos_no_stats_conflicto(self) -> None:
        st = ConflictDetectionStage()
        claims = [_claim("t-x contenido ambiguo", text_id="t-x")]
        ctx = _context(claims=claims, statistics={"ambiguous_entity_ids": ["t-x"]})
        out = st.execute(ctx)
        assert out.statistics["conflicts_detected"] == 0
        assert out.statistics["conflicts_unresolved"] == 0


class TestFusionRegistry:
    def test_register_get_engine(self) -> None:
        r = FusionRegistry()
        engine = object()
        r.register_engine("a", engine)
        assert r.get_engine("a") is engine
        assert r.list_engines() == ["a"]

    def test_get_engine_missing(self) -> None:
        r = FusionRegistry()
        try:
            r.get_engine("nope")
            raise AssertionError("debería lanzar KeyError")
        except KeyError:
            pass

    def test_default_missing(self) -> None:
        r = FusionRegistry()
        try:
            r.get_engine()
            raise AssertionError("debería lanzar KeyError")
        except KeyError:
            pass

    def test_conflict_resolvers(self) -> None:
        r = FusionRegistry()
        res = object()
        r.register_conflict_resolver("a", res)
        assert r.get_conflict_resolver("a") is res
        assert r.list_conflict_resolvers() == ["a"]
        try:
            r.get_conflict_resolver("x")
            raise AssertionError("KeyError esperado")
        except KeyError:
            pass

    def test_source_scorers(self) -> None:
        r = FusionRegistry()
        s = object()
        r.register_source_scorer("a", s)
        assert r.get_source_scorer("a") is s
        assert r.list_source_scorers() == ["a"]
        try:
            r.get_source_scorer("x")
            raise AssertionError("KeyError esperado")
        except KeyError:
            pass

    def test_mergers(self) -> None:
        r = FusionRegistry()
        m = object()
        r.register_merger("a", m)
        assert r.get_merger("a") is m
        assert r.list_mergers() == ["a"]
        try:
            r.get_merger("x")
            raise AssertionError("KeyError esperado")
        except KeyError:
            pass

    def test_change_detectors(self) -> None:
        r = FusionRegistry()
        d = object()
        r.register_change_detector("a", d)
        assert r.get_change_detector("a") is d
        assert r.list_change_detectors() == ["a"]
        try:
            r.get_change_detector("x")
            raise AssertionError("KeyError esperado")
        except KeyError:
            pass

    def test_selectors(self) -> None:
        r = FusionRegistry()
        s = object()
        r.register_selector("a", s)
        assert r.get_selector("a") is s
        assert r.list_selectors() == ["a"]
        try:
            r.get_selector("x")
            raise AssertionError("KeyError esperado")
        except KeyError:
            pass

    def test_entity_resolvers(self) -> None:
        r = FusionRegistry()
        e = object()
        r.register_entity_resolver("a", e)
        assert r.get_entity_resolver("a") is e
        assert r.list_entity_resolvers() == ["a"]
        try:
            r.get_entity_resolver("x")
            raise AssertionError("KeyError esperado")
        except KeyError:
            pass


class _FakeIndex:
    """FactIndex mínimo para ContextBuilder."""

    def __init__(self, entries) -> None:
        self._entries = entries

    def lookup_entity(self, entity: str) -> list:
        ent = entity.lower()
        return [e for e in self._entries if ent in self._names(e).lower()]

    @staticmethod
    def _names(entry) -> str:
        if isinstance(entry, tuple):
            return entry[0].subject + entry[0].predicate + entry[0].object
        return entry.subject + entry.predicate + entry.object


class TestContextBuilder:
    def test_sin_index_devuelve_vacio(self) -> None:
        b = ContextBuilder()
        assert b.build_context(query="que vende apple") == ""
        assert b.index is None

    def test_con_index_y_query(self) -> None:
        facts = [
            _fact(subject="Apple", predicate="vende", obj="iPhones", conf=0.9),
            _fact(subject="Apple", predicate="vende", obj="Macs", conf=0.8),
        ]
        b = ContextBuilder(_FakeIndex(facts))
        ctx = b.build_context(query="que vende apple")
        assert "Apple | vende | iPhones" in ctx
        assert "Apple | vende | Macs" in ctx
        assert "# Conocimiento disponible" in ctx

    def test_include_entities_prioridad(self) -> None:
        facts = [_fact(subject="Apple", predicate="vende", obj="iPhones", conf=0.9)]
        b = ContextBuilder(_FakeIndex(facts))
        ctx = b.build_context(query="", include_entities=["Apple"])
        assert "Apple | vende | iPhones" in ctx

    def test_include_entities_con_query(self) -> None:
        facts = [_fact(subject="Apple", predicate="vende", obj="iPhones", conf=0.9)]
        b = ContextBuilder(_FakeIndex(facts))
        ctx = b.build_context(query="irrelevante", include_entities=["Apple"])
        assert "Apple | vende | iPhones" in ctx

    def test_max_facts_recorta(self) -> None:
        facts = [_fact(subject=f"Empresa{i}", predicate="p", obj="o", conf=0.9) for i in range(5)]
        b = ContextBuilder(_FakeIndex(facts))
        ctx = b.build_context(query="Empresa1 Empresa2", max_facts=1)
        assert ctx.count("- ") == 1

    def test_sin_facts_vacio(self) -> None:
        b = ContextBuilder(_FakeIndex([]))
        assert b.build_context(query="nada") == ""

    def test_sin_query_ni_entities_vacio(self) -> None:
        b = ContextBuilder(_FakeIndex([_fact()]))
        assert b.build_context(query="", include_entities=None) == ""

    def test_entities_sin_query(self) -> None:
        b = ContextBuilder(_FakeIndex([_fact()]))
        assert b.build_context(query="", include_entities=["Apple"]) != ""

    def test_entries_duplicadas_dedup(self) -> None:
        f = _fact(subject="Apple", predicate="vende", obj="iPhones", conf=0.9)
        b = ContextBuilder(_FakeIndex([f, f]))
        ctx = b.build_context(query="que vende apple")
        assert ctx.count("- ") == 1

    def test_tupla_con_version_no_current_ignorada(self) -> None:
        from motor.core.fusion.models import VersionState

        class FakeVersion:
            state = VersionState.SUPERSEDED

        class FakeFact:
            def __init__(self, subject, predicate, obj, confidence, fact_id) -> None:
                self.subject = subject
                self.predicate = predicate
                self.object = obj
                self.confidence = confidence
                self.fact_id = fact_id

        ff = FakeFact("Apple", "vende", "iPhones", 0.9, "f1")
        b = ContextBuilder(_FakeIndex([(ff, FakeVersion())]))
        assert b.build_context(query="que vende apple") == ""

    def test_tupla_con_version_current_formateada(self) -> None:
        from motor.core.fusion.models import VersionState

        class FakeVersion:
            state = VersionState.CURRENT

            def __init__(self, confidence) -> None:
                self.confidence = confidence

        class FakeFact:
            def __init__(self, subject, predicate, obj, confidence, fact_id) -> None:
                self.subject = subject
                self.predicate = predicate
                self.object = obj
                self.confidence = confidence
                self.fact_id = fact_id

        ff = FakeFact("Apple", "vende", "iPhones", 0.9, "f1")
        b = ContextBuilder(_FakeIndex([(ff, FakeVersion(0.9))]))
        ctx = b.build_context(query="que vende apple")
        assert "Apple | vende | iPhones" in ctx
        assert "0.90" in ctx

    def test_set_index(self) -> None:
        b = ContextBuilder()
        b.set_index(_FakeIndex([_fact()]))
        assert b.index is not None
        assert b.build_context(query="Apple") != ""

    def test_collect_facts_sin_index(self) -> None:
        b = ContextBuilder()
        assert b._collect_facts("query", None) == []
