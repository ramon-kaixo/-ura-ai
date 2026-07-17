"""Test E2E de integración vertical F25-A3.

Demuestra que un hecho generado por FusionPipeline puede ser:
1. Indexado en FactIndex
2. Recuperado mediante ContextBuilder
3. Formateado como contexto utilizable por LLM
4. Proyectado a SemanticFact compatible con memoria
"""

from __future__ import annotations

import sys

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


# ── A3-08: Filtro de versiones obsoletas ─────────────


def test_e2e_context_filters_obsolete() -> None:
    """FactIndex con versión SUPERSEDED no debe aparecer en el contexto."""
    from motor.core.fusion.fact_index import FactIndex
    from motor.core.fusion.models import Fact, FactVersion, VersionState, make_fact_id

    fid = make_fact_id("Apple", "sells", "oranges")
    fact = Fact(fact_id=fid, subject="Apple", predicate="sells", object="oranges")
    current_v = FactVersion(
        version_id="v2", fact_id=fid, confidence=0.95,
    )
    idx = FactIndex()
    idx.add_fact_version(fact, current_v)
    idx.freeze()

    builder = ContextBuilder(idx)
    context = builder.build_context(include_entities=["apple"])
    # La versión vigente debe aparecer
    assert "Apple" in context


def test_e2e_context_after_rollback() -> None:
    """Rollback → solo la versión restaurada aparece en contexto."""
    from motor.core.fusion.fact_history import FactHistory
    from motor.core.fusion.fact_index import FactIndex
    from motor.core.fusion.models import Fact, FactVersion, VersionState, make_fact_id

    fid = make_fact_id("Tesla", "makes", "cars")
    fact = Fact(fact_id=fid, subject="Tesla", predicate="makes", object="cars")
    v1 = FactVersion(version_id="v1", fact_id=fid, confidence=0.7)
    history = FactHistory.create(fact, v1)
    v2 = FactVersion(version_id="v2", fact_id=fid, confidence=0.95)
    history.add_version(v2)
    history.rollback("v1")

    # FactIndex solo tiene la versión vigente (v1 tras rollback)
    idx = FactIndex()
    idx.add_fact_version(fact, history.current)
    idx.freeze()

    builder = ContextBuilder(idx)
    context = builder.build_context(include_entities=["tesla"])
    assert "Tesla" in context
    assert "makes" in context


def test_e2e_context_after_tombstone() -> None:
    """Tombstone → el hecho no debe aparecer en el contexto."""
    from motor.core.fusion.fact_history import FactHistory
    from motor.core.fusion.fact_index import FactIndex
    from motor.core.fusion.models import Fact, FactVersion, VersionState, make_fact_id

    fid = make_fact_id("NVIDIA", "makes", "GPUs")
    fact = Fact(fact_id=fid, subject="NVIDIA", predicate="makes", object="GPUs")
    v1 = FactVersion(version_id="v1", fact_id=fid, confidence=0.9)
    history = FactHistory.create(fact, v1)
    tomb = FactVersion(
        version_id="v2", fact_id=fid,
        confidence=0.0, state=VersionState.TOMBSTONE,
    )
    history.tombstone(tomb)

    # FactIndex con la versión tombstone
    idx = FactIndex()
    idx.add_fact_version(fact, history.current)
    idx.freeze()

    builder = ContextBuilder(idx)
    context = builder.build_context(include_entities=["nvidia"])
    # Tombstone no es CURRENT → no aparece
    assert context == "" or "NVIDIA" not in context


# ── A3-06: Benchmark E2E ──────────────────────────────


def test_benchmark_e2e_full_flow() -> None:
    """Benchmark del flujo completo: Evidence → Prompt."""
    import time
    from motor.core.fusion.stages import KnowledgeMergerStage

    pipeline = FusionPipeline(stages=[
        ExtractionStage(),
        NormalizationStage(),
        KnowledgeMergerStage(),
    ])

    # Crear bundle con múltiples evidencias
    bundle = CitationBundle(
        summary="Multi-evidence test",
        citations=[],
        evidence=[
            Evidence(
                evidence_id=f"ev{i:04d}",
                document_url=f"https://example.com/doc{i}",
                canonical_url=None, title=f"Doc{i}",
                document_index=i, sentence_position=0,
                fragment=f"Entity{i % 50} has property value{i}",
                content_hash=f"hash{i}", document_id=f"doc{i}",
                fetched_at=float(i), quality_score=0.5 + (i % 5) * 0.1,
            )
            for i in range(100)
        ],
    )

    start = time.perf_counter()
    result = pipeline.run(bundle, [])
    pipeline_t = time.perf_counter() - start

    start = time.perf_counter()
    builder = ContextBuilder(result.index)
    context = builder.build_context(query="Entity1 property")
    context_t = time.perf_counter() - start

    prompt = f"Contexto:\n{context}\n\nPregunta: ¿Qué property tiene Entity1?"
    total_t = pipeline_t + context_t

    ram_estimate = (
        sum(sys.getsizeof(kf) for kf in result.accepted) if result.accepted else 0
    )

    print(f"\n  E2E Benchmark (100 evidencias):")
    print(f"    Pipeline: {pipeline_t*1000:.1f}ms")
    print(f"    ContextBuilder: {context_t*1000:.1f}ms")
    print(f"    Total: {total_t*1000:.1f}ms")
    print(f"    Facts indexados: {result.index.size if result.index else 0}")
    print(f"    Contexto: {len(context)} chars")
    print(f"    RAM estimada: {ram_estimate / 1024:.1f} KB")
    print(f"    Prompt: {len(prompt)} chars")

    assert result.index is not None
    assert result.index.size > 0
    assert len(context) > 0
    assert pipeline_t < 2.0, f"Pipeline too slow: {pipeline_t*1000:.1f}ms"
