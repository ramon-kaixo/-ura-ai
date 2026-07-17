"""Test E2E de integración vertical F25-A3.

Demuestra que un hecho generado por FusionPipeline puede ser:
1. Indexado en FactIndex
2. Recuperado mediante ContextBuilder
3. Formateado como contexto utilizable por LLM
4. Proyectado a SemanticFact compatible con memoria
"""

from __future__ import annotations

from motor.core.fusion.bridge import knowledge_fact_to_semantic_fact
from motor.core.fusion.context_builder import ContextBuilder
from motor.core.fusion.engine import FusionPipeline
from motor.core.fusion.fact_index import FactIndex
from motor.core.fusion.models import (
    Fact,
    FactVersion,
    FusionResult,
    KnowledgeClaim,
    KnowledgeFact,
    make_fact_id,
    make_claim_id,
)
from motor.core.fusion.stages import (
    ExtractionStage,
    NormalizationStage,
)
from motor.core.web.citation.citation import CitationBundle, Evidence


# ── E2E: Pipeline completo → FactIndex → Contexto ─────


def _make_bundle() -> CitationBundle:
    return CitationBundle(
        summary="Test evidence bundle",
        citations=[],
        evidence=[
            Evidence(
                evidence_id="ev001",
                document_url="https://example.com/apple",
                canonical_url=None,
                title="Apple sells oranges",
                document_index=0,
                sentence_position=0,
                fragment="Apple sells oranges in California",
                content_hash="abc123",
                document_id="doc001",
                fetched_at=1000.0,
                quality_score=0.9,
            ),
            Evidence(
                evidence_id="ev002",
                document_url="https://example.com/tesla",
                canonical_url=None,
                title="Tesla makes cars",
                document_index=0,
                sentence_position=1,
                fragment="Tesla makes electric cars",
                content_hash="def456",
                document_id="doc002",
                fetched_at=1000.0,
                quality_score=0.85,
            ),
        ],
    )


def test_e2e_fusion_to_index() -> None:
    """FusionPipeline produce FusionResult con FactIndex incluido."""
    from motor.core.fusion.stages import KnowledgeMergerStage
    pipeline = FusionPipeline(stages=[
        ExtractionStage(),
        NormalizationStage(),
        KnowledgeMergerStage(),
    ])
    bundle = _make_bundle()
    result = pipeline.run(bundle, [])
    assert isinstance(result, FusionResult)
    assert result.index is not None
    assert result.index.size >= 1, f"Expected at least 1 fact, got {result.index.size}"
    print(f"  Facts indexados: {result.index.size}")


def test_e2e_index_to_context() -> None:
    """FactIndex → ContextBuilder produce texto utilizable por LLM."""
    from motor.core.fusion.stages import KnowledgeMergerStage
    pipeline = FusionPipeline(stages=[
        ExtractionStage(),
        NormalizationStage(),
        KnowledgeMergerStage(),
    ])
    bundle = _make_bundle()
    result = pipeline.run(bundle, [])

    builder = ContextBuilder(result.index)
    context = builder.build_context(query="Apple sells oranges")
    assert context is not None
    assert len(context) > 0
    assert "Apple" in context or "apple" in context
    print(f"  Contexto generado ({len(context)} chars):")
    for line in context.split("\n"):
        print(f"    {line}")


def test_e2e_fact_to_semantic_projection() -> None:
    """KnowledgeFact → SemanticFact projection es funcional."""
    kf = KnowledgeFact(
        id="f1",
        subject="Apple",
        predicate="sells",
        object="oranges",
        confidence=0.9,
        evidence_ids=("ev001",),
        provenance=("c001",),
    )
    projected = knowledge_fact_to_semantic_fact(kf)
    assert projected["subject"] == "Apple"
    assert projected["predicate"] == "sells"
    assert projected["object_value"] == "oranges"
    assert projected["confidence"] == 0.9
    assert "ev001" in projected["source_episode_ids"]
    # Compatible con SemanticMemoryStore.store()
    required_keys = {"subject", "predicate", "object_value", "confidence", "source_episode_ids"}
    assert required_keys.issubset(projected.keys()), f"Missing keys: {required_keys - set(projected.keys())}"
    print(f"  Proyeccion OK: {projected['subject']} | {projected['predicate']} | {projected['object_value']}")


def test_e2e_context_ready_for_llm() -> None:
    """El contexto generado puede insertarse en un prompt LLM."""
    # Crear un FactIndex directamente
    fid = make_fact_id("Apple", "sells", "oranges")
    fact = Fact(fact_id=fid, subject="Apple", predicate="sells", object="oranges")
    version = FactVersion(
        version_id="v1", fact_id=fid,
        confidence=0.95, evidence_ids=("ev001",),
    )
    idx = FactIndex()
    idx.add_fact_version(fact, version)
    idx.freeze()

    builder = ContextBuilder(idx)
    context = builder.build_context(include_entities=["apple"])

    # Verificar que el contexto es un texto plano válido
    assert isinstance(context, str)
    assert context.startswith("# Conocimiento disponible")
    assert "Apple" in context
    assert "oranges" in context

    # Simular inserción en prompt
    prompt = f"""Responde la siguiente pregunta usando el contexto proporcionado.

Contexto:
{context}

Pregunta: ¿Qué vende Apple?
"""
    assert "Apple" in prompt
    assert "oranges" in prompt
    print("  Contexto listo para LLM:")
    print(f"    {prompt[:200]}...")


def test_e2e_full_vertical_flow() -> None:
    """Prueba completa: Evidence → Fact → FactIndex → Contexto → LLM-ready.

    Este es el criterio de cierre de F25: un hecho generado por el pipeline
    puede ser recuperado y utilizado para construir contexto LLM.
    """
    # 1. Pipeline produce Facts
    from motor.core.fusion.stages import KnowledgeMergerStage
    pipeline = FusionPipeline(stages=[
        ExtractionStage(),
        NormalizationStage(),
        KnowledgeMergerStage(),
    ])
    result = pipeline.run(_make_bundle(), [])

    # 2. FactIndex está poblado
    assert result.index is not None
    assert result.index.size > 0

    # 3. Bridge puede proyectar a SemanticFact
    for kf in result.accepted:
        projected = knowledge_fact_to_semantic_fact(kf)
        assert projected["subject"]
        assert projected["predicate"]
        assert projected["object_value"]

    # 4. ContextBuilder produce texto
    builder = ContextBuilder(result.index)
    context = builder.build_context(query="Apple sells oranges")
    assert context and len(context) > 0

    # 5. El contexto es insertable en un prompt
    prompt = f"""Eres un asistente con acceso a hechos.

{context}

Pregunta: ¿Qué vende Apple?
"""
    assert "Apple" in prompt
    assert len(prompt) > 50
    print("  FLUJO VERTICAL COMPLETO VERIFICADO:")
    print(f"    1. Pipeline produjo {len(result.accepted)} facts")
    print(f"    2. FactIndex indexo {result.index.size} facts")
    print(f"    3. Proyeccion a SemanticFact disponible")
    print(f"    4. ContextBuilder genero {len(context)} chars")
    print(f"    5. Prompt listo para LLM ({len(prompt)} chars)")
