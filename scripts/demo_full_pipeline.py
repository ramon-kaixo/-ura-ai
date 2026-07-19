#!/usr/bin/env python3
"""URA Demo — Pipeline completo: Documento → LLM.

Ajusta sys.path para encontrar motor/ desde scripts/.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Flujo vertical: Documento (simulado) -> F24 -> F25 -> F26 -> F27 -> LLM

import time

# Colores para output
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
END = "\033[0m"

VERBOSE = "--verbose" in sys.argv


def log(step: str, msg: str = "") -> None:
    print(f"\n{BOLD}{GREEN}▶ {step}{END}")
    if msg:
        print(f"  {msg}")


def debug(msg: str) -> None:
    if VERBOSE:
        print(f"  {BLUE}{msg}{END}")


def main() -> None:
    print(f"\n{BOLD}{'='*60}{END}")
    print(f"{BOLD}  URA — DEMO: Pipeline Completo de Conocimiento{END}")
    print(f"{BOLD}{'='*60}{END}")
    start = time.perf_counter()

    # ── Paso 1: Documentos fuente ──
    log("PASO 1: Documentos fuente (F24 Web Intelligence)",
        "3 documentos sobre tecnología simulados")

    documents = [
        "Apple Inc. reported record revenue of $124.3 billion in Q1 2026, driven by iPhone and Services growth.",
        "Tim Cook announced Apple's new AI strategy during the keynote at Cupertino headquarters.",
        "Tesla delivered 1.8 million electric vehicles in 2025, exceeding analyst expectations.",
    ]
    for i, doc in enumerate(documents):
        debug(f"  Doc {i+1}: {doc[:60]}...")

    # ── Paso 2: CitationBundle (simula F24) ──
    log("PASO 2: CitationBundle con evidencias (F24)",
         "Extrayendo fragmentos con calidad >0.7")

    from motor.core.web.citation.citation import CitationBundle, Evidence

    bundle = CitationBundle(
        summary="Technology company earnings and strategy",
        citations=[],
        evidence=[
            Evidence(
                evidence_id=f"ev{i:04d}",
                document_url=f"https://example.com/article{i}",
                canonical_url=None,
                title=f"Article {i}",
                document_index=i,
                sentence_position=0,
                fragment=doc,
                content_hash=f"hash{i:04d}",
                document_id=f"doc{i:04d}",
                fetched_at=1000.0 + i,
                quality_score=0.75 + (i * 0.05),
            )
            for i, doc in enumerate(documents)
        ],
    )
    print(f"     → {len(bundle.evidence)} evidencias extraídas")

    # ── Paso 3: FusionPipeline (F25) ──
    log("PASO 3: Knowledge Fusion (F25)",
        "Pipeline: Extracción → Normalización → Merge → Memoria")

    from motor.core.fusion.engine import FusionPipeline
    from motor.core.fusion.stages import (
        ExtractionStage,
        KnowledgeMergerStage,
        MemoryCandidateSelectionStage,
        NormalizationStage,
    )

    pipeline = FusionPipeline(stages=[
        ExtractionStage(),
        NormalizationStage(),
        KnowledgeMergerStage(),
        MemoryCandidateSelectionStage(),
    ])

    import os
    import tempfile

    from motor.memory import Memory
    tmpdir = tempfile.mkdtemp(prefix="ura_demo_")
    snap = os.path.join(tmpdir, "snap.json")
    journal = os.path.join(tmpdir, "journal.jsonl")
    memory = Memory(snapshot_path=snap, journal_path=journal)

    from motor.core.fusion.models import FusionContext
    ctx = FusionContext(bundle=bundle)
    ctx.statistics["_memory_instance"] = memory

    t0 = time.perf_counter()
    for stage in pipeline._stages:
        ctx = stage.execute(ctx)
    fusion_time = time.perf_counter() - t0

    facts_count = len(ctx.facts)
    claims_count = len(ctx.claims)
    print(f"     → {facts_count} KnowledgeFacts generados en {fusion_time*1000:.1f}ms")
    print(f"     → {claims_count} Claims procesados")
    print(f"     → {len(ctx.entities)} entidades resueltas")

    for i, fact in enumerate(ctx.facts):
        print(f"       Fact {i+1}: {fact.subject} | {fact.predicate} | {fact.object} "
              f"(confianza: {fact.confidence:.2f})")

    # ── Paso 4: Memory (F26) ──
    log("PASO 4: Memoria Histórica (F26)",
        "Escribiendo Facts en la línea temporal")

    memory_entries = memory.timeline.size
    memory.snapshot("demo_v1")
    print(f"     → {memory_entries} entries en MemoryTimeline")
    print("     → Snapshot guardado")

    # ── Paso 5: Context Builder → Prompt LLM (F27) ──
    log("PASO 5: Contexto para LLM (F27)",
        "Construyendo prompt a partir de Facts fusionados")

    from motor.core.fusion.context_builder import ContextBuilder

    # Reconstruir FactIndex desde el pipeline
    result = pipeline.run(bundle, [])
    if result.index is None:
        print(f"     {RED}⚠ No se pudo construir FactIndex{END}")
        # Fallback: construir manualmente
        from motor.core.fusion.fact_index import FactIndex
        from motor.core.fusion.models import Fact, FactVersion, make_fact_id
        idx = FactIndex()
        for kf in ctx.facts:
            fid = make_fact_id(kf.subject, kf.predicate, kf.object)
            fact = Fact(fact_id=fid, subject=kf.subject, predicate=kf.predicate, object=kf.object)
            ver = FactVersion(
                version_id=f"v{kf.version}", fact_id=fid,
                confidence=kf.confidence, evidence_ids=kf.evidence_ids,
                provenance=kf.provenance, created_at=kf.created_at or 0.0,
            )
            idx.add_fact_version(fact, ver)
        idx.freeze()
        result_index = idx
    else:
        result_index = result.index

    builder = ContextBuilder(result_index)

    # Consultas de ejemplo
    queries = [
        "Apple revenue and strategy",
        "Tesla vehicle deliveries",
        "technology company performance",
    ]

    for query in queries:
        context = builder.build_context(query=query, max_facts=5)
        if context:
            word_count = len(context.split())
            print(f"\n  {YELLOW}Consulta: '{query}'{END}")
            print(f"  Contexto generado: {word_count} palabras, {len(context)} chars")
            if VERBOSE:
                print(f"  {context[:300]}...")
        else:
            print(f"  {YELLOW}Consulta: '{query}' → sin resultados relevantes{END}")

    # ── Paso 6: Prompt final listo para LLM ──
    log("PASO 6: Prompt listo para LLM",
        "Contexto formateado para enviar a cualquier LLM")

    context_all = builder.build_context(max_facts=10)

    prompt = f"""{BOLD}System:{END} Eres un asistente con acceso a los siguientes hechos.

{context_all}

Pregunta: ¿Qué empresas tecnológicas reportaron resultados y cuáles fueron sus métricas clave?
"""

    print("\n  Prompt final:")
    print(f"  {'─'*50}")
    for line in prompt.strip().split("\n")[:8]:
        print(f"  {line}")
    print(f"  {'─'*50}")
    print(f"  → Prompt listo: {len(prompt)} chars, ~{len(prompt.split())} tokens approx")

    # ── Resumen ──
    total_time = time.perf_counter() - start
    print(f"\n{BOLD}{'='*60}{END}")
    print(f"{BOLD}  DEMO COMPLETADA{END}")
    print(f"  Tiempo total: {total_time*1000:.1f}ms")
    print(f"  Facts: {facts_count} | Memoria: {memory_entries} | Prompt: {len(prompt)} chars")
    print("  Pipeline completo: Documento → Evidence → Fact → Memory → Contexto → LLM")
    print(f"{BOLD}{'='*60}{END}\n")

    # Limpieza
    import shutil
    memory.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
