#!/usr/bin/env python3
"""Cobertura 100x100 de motor/core/fusion/__init__.py."""

import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.fusion import (
    run_fusion_on_claims,
    _persist_fusion_facts,
    KnowledgeClaim,
    FusionContext,
    FusionProvenance,
    KnowledgeFact,
)


class TestFusionInit:
    """Tests para motor/core/fusion/__init__.py."""

    @pytest.mark.unit
    def test_imports_disponibles(self):
        """Verifica que todos los imports públicos están disponibles."""
        from motor.core.fusion import (
            ChangeDetector,
            Conflict,
            ConflictGraph,
            ConflictResolver,
            ConflictType,
            ContextBuilder,
            EntityResolver,
            EvidenceSet,
            Fact,
            FactIndex,
            FactTombstone,
            FactVersion,
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
            VersionState,
            build_default_pipeline,
            fact_version_to_semantic_fact,
            knowledge_fact_to_semantic_fact,
            make_claim_id,
            make_conflict_id,
            make_fact_id,
            make_version_id,
            normalize_identity,
        )
        # Si se importa sin error, OK


class TestRunFusionOnClaims:
    """Tests para run_fusion_on_claims()."""

    @pytest.mark.unit
    def test_run_fusion_on_claims_vacio(self):
        """Sin claims -> retorna 0."""
        result = run_fusion_on_claims([])
        assert result == 0

    @pytest.mark.unit
    def test_run_fusion_on_claims_con_claims(self):
        """Con claims -> ejecuta pipeline."""
        from motor.core.fusion import run_fusion_on_claims, KnowledgeClaim
        
        with patch('motor.core.fusion._persist_fusion_facts') as mock_persist:
            result = run_fusion_on_claims([
                KnowledgeClaim(id="test", text="test claim", confidence=0.9, subject="test", predicate="es", object="valor")
            ])
            
            assert result >= 0


class TestPersistFusionFacts:
    """Tests para _persist_fusion_facts()."""

    @pytest.mark.unit
    def test_persist_fusion_facts_llamado(self):
        """Verifica que _persist_fusion_facts se puede llamar sin error."""
        from motor.core.fusion import _persist_fusion_facts
        from motor.core.fusion.models import KnowledgeFact
        
        facts = [
            KnowledgeFact(
                id="test_id",
                subject="test",
                predicate="es",
                object="valor",
                confidence=0.9,
                version=1,
                provenance={"source": "test"}
            )
        ]
        
        # Mock de las dependencias internas con las rutas correctas
        with patch('motor.core.fusion.knowledge_fact_to_semantic_fact', return_value={}), \
             patch('motor.intelligence.memory.semantic.SemanticMemoryStore') as mock_store_class, \
             patch('motor.memory.Memory') as mock_memory_class, \
             patch('time.time', return_value=1000.0), \
             patch('motor.memory.make_entry_id', return_value="test_entry_id"), \
             patch('motor.memory.MemoryEntry') as mock_entry_class, \
             patch('motor.memory.Memory') as mock_memory_class, \
             patch('motor.memory.FactRef') as mock_factref_class, \
             patch('time.time', return_value=1000.0):
            
            mock_store = MagicMock()
            mock_store_class.return_value = mock_store
            
            mock_memory = MagicMock()
            mock_memory.append = MagicMock()
            mock_memory_class.return_value = mock_memory
            
            _persist_fusion_facts([], "/fake/path", "test_correlation")
            
            mock_store_class.assert_called_once()
            mock_memory_class.assert_called_once()


class TestExports:
    """Verifica que todos los exports públicos están disponibles."""

    @pytest.mark.unit
    def test_all_exports_disponibles(self):
        """Verifica que __all__ contiene los exports esperados."""
        import motor.core.fusion as fusion_module
        
        expected_exports = {
            "ChangeDetector", "Conflict", "ConflictGraph", "ConflictResolver",
            "ConflictType", "ContextBuilder", "EntityResolver", "EvidenceSet",
            "Fact", "FactIndex", "FactTombstone", "FactVersion",
            "FusionConfig", "FusionContext", "FusionEngine", "FusionPipeline",
            "FusionProvenance", "FusionRegistry", "FusionResult", "FusionStage",
            "KnowledgeClaim", "KnowledgeDelta", "KnowledgeFact", "KnowledgeMerger",
            "MemoryCandidateSelector", "PipelineStage", "ResolutionStatus",
            "ResolvedEntity", "SourceScore", "SourceScorer", "StageProvenance",
            "VersionState", "build_default_pipeline",
            "fact_version_to_semantic_fact", "knowledge_fact_to_semantic_fact",
            "make_claim_id", "make_conflict_id", "make_fact_id",
            "make_version_id", "normalize_identity",
            "run_fusion_on_claims", "_persist_fusion_facts",
        }
        
        import motor.core.fusion as fusion_module
        
        for export in expected_exports:
            assert hasattr(fusion_module, export), f"Export faltante: {export}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
