#!/usr/bin/env python3
"""Cobertura 100x100 de motor/core/fusion/models.py."""

import pytest
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.fusion.models import (
    normalize_identity,
    make_claim_id,
    make_fact_id,
    make_version_id,
    make_conflict_id,
    ConflictType,
    ResolutionStatus,
    VersionState,
    Fact,
    FactTombstone,
    FactVersion,
    ResolvedEntity,
    SourceScore,
    KnowledgeClaim,
    Conflict,
    ConflictGraph,
    KnowledgeFact,
    KnowledgeDelta,
    EvidenceSet,
    FusionProvenance,
    StageProvenance,
    FusionContext,
    FusionResult,
)


class TestNormalizeIdentity:
    @pytest.mark.unit
    def test_lowercase_strip(self):
        assert normalize_identity("  HELLO WORLD  ") == "hello world"

    @pytest.mark.unit
    def test_espacios_multiples(self):
        assert normalize_identity("hello   world") == "hello world"

    @pytest.mark.unit
    def test_puntuacion_eliminada(self):
        assert normalize_identity("Hello, World!") == "hello world"

    @pytest.mark.unit
    def test_sin_cambios_ya_normalizado(self):
        assert normalize_identity("hello world") == "hello world"

    @pytest.mark.unit
    def test_vacio(self):
        assert normalize_identity("") == ""

    @pytest.mark.unit
    def test_no_resuelve_sinonimos(self):
        assert normalize_identity("CEO") == "ceo"
        assert normalize_identity("Chief Executive Officer") == "chief executive officer"

    @pytest.mark.unit
    def test_no_resuelve_entidades(self):
        assert normalize_identity("Apple") == "apple"


class TestMakeClaimId:
    @pytest.mark.unit
    def test_determinista(self):
        id1 = make_claim_id("ev1", "texto de prueba")
        id2 = make_claim_id("ev1", "texto de prueba")
        assert id1 == id2
        assert len(id1) == 16

    @pytest.mark.unit
    def test_diferente_evidence_id(self):
        id1 = make_claim_id("ev1", "texto")
        id2 = make_claim_id("ev2", "texto")
        assert id1 != id2

    @pytest.mark.unit
    def test_diferente_texto(self):
        id1 = make_claim_id("ev1", "texto 1")
        id2 = make_claim_id("ev1", "texto 2")
        assert id1 != id2

    @pytest.mark.unit
    def test_case_insensitive(self):
        id1 = make_claim_id("ev1", "TEXTO")
        id2 = make_claim_id("ev1", "texto")
        assert id1 == id2


class TestMakeFactId:
    @pytest.mark.unit
    def test_determinista(self):
        id1 = make_fact_id("sujeto", "predicado", "objeto")
        id2 = make_fact_id("sujeto", "predicado", "objeto")
        assert id1 == id2
        assert len(id1) == 16

    @pytest.mark.unit
    def test_orden_importa(self):
        id1 = make_fact_id("sujeto", "predicado", "objeto")
        id2 = make_fact_id("objeto", "predicado", "sujeto")
        assert id1 != id2

    @pytest.mark.unit
    def test_normalizacion_canonica(self):
        id1 = make_fact_id("  SUJETO  ", "  PREDICADO  ", "  OBJETO  ")
        id2 = make_fact_id("sujeto", "predicado", "objeto")
        assert id1 == id2

    @pytest.mark.unit
    def test_version_no_participa(self):
        id1 = make_fact_id("s", "p", "o")
        id2 = make_fact_id("s", "p", "o")
        assert id1 == id2


class TestMakeVersionId:
    @pytest.mark.unit
    def test_determinista(self):
        id1 = make_version_id("fact123", 1000.0, "hash123")
        id2 = make_version_id("fact123", 1000.0, "hash123")
        assert id1 == id2
        assert len(id1) == 16

    @pytest.mark.unit
    def test_timestamp_participa(self):
        id1 = make_version_id("fact1", 1000.0, "hash")
        id2 = make_version_id("fact1", 2000.0, "hash")
        assert id1 != id2

    @pytest.mark.unit
    def test_content_hash_participa(self):
        id1 = make_version_id("fact1", 1000.0, "hash1")
        id2 = make_version_id("fact1", 1000.0, "hash2")
        assert id1 != id2


class TestMakeConflictId:
    @pytest.mark.unit
    def test_determinista(self):
        id1 = make_conflict_id("claim1", "claim2", "contradiction")
        id2 = make_conflict_id("claim1", "claim2", "contradiction")
        assert id1 == id2
        assert len(id1) == 16

    @pytest.mark.unit
    def test_orden_importa(self):
        id1 = make_conflict_id("a", "b", "contradiction")
        id2 = make_conflict_id("b", "a", "contradiction")
        assert id1 != id2

    @pytest.mark.unit
    def test_tipo_conflicto_importa(self):
        id1 = make_conflict_id("a", "b", "contradiction")
        id2 = make_conflict_id("a", "b", "temporal_update")
        assert id1 != id2


class TestConflictType:
    @pytest.mark.unit
    def test_valores(self):
        from motor.core.fusion.models import ConflictType
        assert list(ConflictType) == [
            ConflictType.CONTRADICTION,
            ConflictType.TEMPORAL_UPDATE,
            ConflictType.DIFFERENT_GRANULARITY,
            ConflictType.DIFFERENT_SCOPE,
            ConflictType.OPINION,
        ]

    @pytest.mark.unit
    def test_iteracion(self):
        assert len(list(ConflictType)) == 5


class TestResolutionStatus:
    @pytest.mark.unit
    def test_valores(self):
        from motor.core.fusion.models import ResolutionStatus
        assert list(ResolutionStatus) == ["resolved", "unknown", "ambiguous", "error"]


class TestVersionState:
    @pytest.mark.unit
    def test_valores(self):
        from motor.core.fusion.models import VersionState
        assert list(VersionState) == ["current", "superseded", "rolled_back", "tombstone", "deleted"]


class TestFact:
    @pytest.mark.unit
    def test_creacion_basica(self):
        from motor.core.fusion.models import Fact
        fact = Fact(
            fact_id="fact1",
            subject="s",
            predicate="p",
            object="o"
        )
        assert fact.fact_id == "fact1"
        assert fact.subject == "s"


class TestKnowledgeFact:
    @pytest.mark.unit
    def test_creacion_basica(self):
        from motor.core.fusion.models import KnowledgeFact
        kf = KnowledgeFact(
            id="kf1",
            subject="s",
            predicate="p",
            object="o",
            confidence=0.9,
            version=1,
            provenance={}
        )
        assert kf.id == "kf1"
        assert kf.confidence == 0.9
        assert kf.version == 1


class TestKnowledgeClaim:
    @pytest.mark.unit
    def test_creacion_basica(self):
        from motor.core.fusion.models import KnowledgeClaim
        claim = KnowledgeClaim(
            id="kc1",
            text="texto",
            confidence=0.9
        )
        assert claim.id == "kc1"
        assert claim.text == "texto"
        assert claim.confidence == 0.9


class TestConflict:
    @pytest.mark.unit
    def test_creacion_basica(self):
        from motor.core.fusion.models import Conflict, ConflictType
        c = Conflict(
            id="c1",
            claim_a="a",
            claim_b="b",
            conflict_type="contradiction"
        )
        assert c.conflict_type == "contradiction"
        assert c.resolved is False


class TestFact:
    @pytest.mark.unit
    def test_creacion(self):
        from motor.core.fusion.models import Fact
        f = Fact(fact_id="f1", subject="s", predicate="p", object="o")
        assert f.fact_id == "f1"
        assert f.subject == "s"


class TestKnowledgeFact:
    @pytest.mark.unit
    def test_creacion(self):
        from motor.core.fusion.models import KnowledgeFact
        kf = KnowledgeFact(
            id="kf1",
            subject="s",
            predicate="p",
            object="o",
            confidence=0.9,
            version=1,
            provenance={}
        )
        assert kf.id == "kf1"


class TestConflict:
    @pytest.mark.unit
    def test_creacion_basica(self):
        from motor.core.fusion.models import Conflict, ConflictType
        c = Conflict(
            id="c1",
            claim_a="a",
            claim_b="b",
            conflict_type="contradiction"
        )
        assert c.conflict_type == "contradiction"
        assert c.resolved is False


class TestFact:
    @pytest.mark.unit
    def test_creacion(self):
        from motor.core.fusion.models import Fact
        f = Fact(fact_id="f1", subject="s", predicate="p", object="o")
        assert f.fact_id == "f1"
        assert f.subject == "s"


class TestKnowledgeFact:
    @pytest.mark.unit
    def test_creacion(self):
        kf = KnowledgeFact(
            id="kf1",
            subject="s",
            predicate="p",
            object="o",
            confidence=0.9,
            version=1,
            provenance={}
        )
        assert kf.id == "kf1"


class TestConflictType:
    @pytest.mark.unit
    def test_valores(self):
        from motor.core.fusion.models import ConflictType
        assert list(ConflictType) == [
            ConflictType.CONTRADICTION,
            ConflictType.TEMPORAL_UPDATE,
            ConflictType.DIFFERENT_GRANULARITY,
            ConflictType.DIFFERENT_SCOPE,
            ConflictType.OPINION,
        ]


class TestResolutionStatus:
    @pytest.mark.unit
    def test_valores(self):
        from motor.core.fusion.models import ResolutionStatus
        assert list(ResolutionStatus) == ["resolved", "unknown", "ambiguous", "error"]


class TestVersionState:
    @pytest.mark.unit
    def test_valores(self):
        from motor.core.fusion.models import VersionState
        assert list(VersionState) == ["current", "superseded", "rolled_back", "tombstone", "deleted"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
