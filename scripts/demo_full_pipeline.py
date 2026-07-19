#!/usr/bin/env python3
"""URA Demo — Pipeline completo: Documento → LLM.

Ajusta sys.path para encontrar motor/ desde scripts/.
"""

import os
import sys

sys.path.insert(0, os.path.join(Path(__file__).parent, ".."))  # noqa: F821, PTH118

# Flujo vertical: Documento (simulado) -> F24 -> F25 -> F26 -> F27 -> LLM

import time
from pathlib import Path

# Colores para output
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
END = "\033[0m"

VERBOSE = "--verbose" in sys.argv


def log(step: str, msg: str = "") -> None:
    if msg:
        pass


def debug(msg: str) -> None:
    if VERBOSE:
        pass


def main() -> None:  # noqa: PLR0915
    start = time.perf_counter()

    # ── Paso 1: Documentos fuente ──
    log("PASO 1: Documentos fuente (F24 Web Intelligence)", "3 documentos sobre tecnología simulados")

    documents = [
        "Apple Inc. reported record revenue of $124.3 billion in Q1 2026, driven by iPhone and Services growth.",
        "Tim Cook announced Apple's new AI strategy during the keynote at Cupertino headquarters.",
        "Tesla delivered 1.8 million electric vehicles in 2025, exceeding analyst expectations.",
    ]
    for i, doc in enumerate(documents):
        debug(f"  Doc {i + 1}: {doc[:60]}...")

    # ── Paso 2: CitationBundle (simula F24) ──
    log("PASO 2: CitationBundle con evidencias (F24)", "Extrayendo fragmentos con calidad >0.7")

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

    # ── Paso 3: FusionPipeline (F25) ──
    log("PASO 3: Knowledge Fusion (F25)", "Pipeline: Extracción → Normalización → Merge → Memoria")

    from motor.core.fusion.engine import FusionPipeline
    from motor.core.fusion.stages import (
        ExtractionStage,
        KnowledgeMergerStage,
        MemoryCandidateSelectionStage,
        NormalizationStage,
    )

    pipeline = FusionPipeline(
        stages=[
            ExtractionStage(),
            NormalizationStage(),
            KnowledgeMergerStage(),
            MemoryCandidateSelectionStage(),
        ],
    )

    import tempfile

    from motor.memory import Memory

    tmpdir = tempfile.mkdtemp(prefix="ura_demo_")
    snap = Path(tmpdir) / "snap.json"
    journal = Path(tmpdir) / "journal.jsonl"
    memory = Memory(snapshot_path=snap, journal_path=journal)

    from motor.core.fusion.models import FusionContext

    ctx = FusionContext(bundle=bundle)
    ctx.statistics["_memory_instance"] = memory

    t0 = time.perf_counter()
    for stage in pipeline._stages:  # noqa: SLF001
        ctx = stage.execute(ctx)
    time.perf_counter() - t0

    len(ctx.facts)
    len(ctx.claims)

    for i, fact in enumerate(ctx.facts):  # noqa: B007
        pass

    # ── Paso 4: Memory (F26) ──
    log("PASO 4: Memoria Histórica (F26)", "Escribiendo Facts en la línea temporal")

    memory.snapshot("demo_v1")

    # ── Paso 5: Context Builder → Prompt LLM (F27) ──
    log("PASO 5: Contexto para LLM (F27)", "Construyendo prompt a partir de Facts fusionados")

    from motor.core.fusion.context_builder import ContextBuilder

    # Reconstruir FactIndex desde el pipeline
    result = pipeline.run(bundle, [])
    if result.index is None:
        # Fallback: construir manualmente
        from motor.core.fusion.fact_index import FactIndex
        from motor.core.fusion.models import Fact, FactVersion, make_fact_id

        idx = FactIndex()
        for kf in ctx.facts:
            fid = make_fact_id(kf.subject, kf.predicate, kf.object)
            fact = Fact(fact_id=fid, subject=kf.subject, predicate=kf.predicate, object=kf.object)
            ver = FactVersion(
                version_id=f"v{kf.version}",
                fact_id=fid,
                confidence=kf.confidence,
                evidence_ids=kf.evidence_ids,
                provenance=kf.provenance,
                created_at=kf.created_at or 0.0,
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
            len(context.split())
            if VERBOSE:
                pass
        else:
            pass

    # ── Paso 6: Prompt final listo para LLM ──
    log("PASO 6: Prompt listo para LLM", "Contexto formateado para enviar a cualquier LLM")

    context_all = builder.build_context(max_facts=10)

    prompt = f"""{BOLD}System:{END} Eres un asistente con acceso a los siguientes hechos.

{context_all}

Pregunta: ¿Qué empresas tecnológicas reportaron resultados y cuáles fueron sus métricas clave?
"""

    for _line in prompt.strip().split("\n")[:8]:
        pass

    # ── Resumen ──
    time.perf_counter() - start

    # Limpieza
    import shutil

    memory.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
