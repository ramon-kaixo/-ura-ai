#!/usr/bin/env python3
"""Generador de datos sintéticos para pruebas de URA.

Útil para:
- Probar el pipeline completo sin depender de fuentes reales
- Benchmarks con volumen controlado
- Tests de integración y estrés
- Reproducir bugs con datasets conocidos

Uso:
  python3 scripts/generate_synthetic_data.py --help
"""

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

rng = random.Random(42)  # seed fija para reproducibilidad


def make_evidence(doc_id: int, text: str, quality: float) -> dict:
    import hashlib
    eid = hashlib.sha256(f"ev{doc_id}:{text[:32]}".encode()).hexdigest()[:16]
    return {
        "evidence_id": eid,
        "document_url": f"https://example.com/doc{doc_id}",
        "canonical_url": None,
        "title": f"Document {doc_id}",
        "document_index": doc_id,
        "sentence_position": 0,
        "fragment": text,
        "content_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
        "document_id": f"doc{doc_id:04d}",
        "fetched_at": 1000.0 + doc_id,
        "quality_score": quality,
    }


def knowledge_domain(num_docs: int = 10) -> list[dict]:
    """Datos sintéticos de tipo 'conocimiento general'."""
    entities = ["Apple", "Tesla", "Microsoft", "Google", "Amazon", "Meta", "NVIDIA", "OpenAI"]
    predicates = ["develops", "sells", "announced", "released", "acquired", "invested_in", "partnered_with"]
    objects = [
        "AI platform", "cloud service", "electric vehicle", "smartphone",
        "operating system", "chip design", "language model", "search engine",
        "social network", "gaming console", "quantum computer", "robotics division",
    ]

    evidence = []
    for i in range(num_docs):
        e = rng.choice(entities)
        p = rng.choice(predicates)
        o = rng.choice(objects)
        quality = round(rng.uniform(0.5, 0.95), 2)
        text = f"{e} {p} {o} in Q{rng.randint(1,4)} 2026"
        evidence.append(make_evidence(i, text, quality))

    return evidence


def financial_domain(num_docs: int = 10) -> list[dict]:
    """Datos sintéticos financieros con números realistas."""
    companies = ["Apple Inc.", "Microsoft Corp.", "Tesla Inc.", "Amazon.com Inc.", "Alphabet Inc."]
    metrics = ["revenue", "profit", "EPS", "gross margin", "operating income"]
    values = [f"${random.uniform(1, 500):.1f}B", f"${random.uniform(0.1, 100):.1f}B",
              f"${random.uniform(1, 20):.2f}", f"{random.uniform(30, 70):.1f}%",
              f"${random.uniform(0.5, 150):.1f}B"]

    evidence = []
    for i in range(num_docs):
        c = rng.choice(companies)
        m = rng.choice(metrics)
        v = rng.choice(values)
        quality = round(rng.uniform(0.7, 0.99), 2)
        text = f"{c} reported {m} of {v} for fiscal year 2026"
        evidence.append(make_evidence(i, text, quality))

    return evidence


def conflict_domain(num_pairs: int = 5) -> list[dict]:
    """Datos con contradicciones para probar conflict resolution."""
    topics = [
        ("Apple", "headquarters", ["Cupertino", "California", "Sunnyvale"]),
        ("Tesla", "CEO", ["Elon Musk", "Elon Reeve Musk", "Tim Cook"]),
        ("Amazon", "revenue", ["$500B", "$514B", "$480B"]),
        ("NVIDIA", "market_cap", ["$2T", "$2.5T", "$3T"]),
        ("Microsoft", "owns", ["GitHub", "LinkedIn", "TikTok"]),
    ]

    evidence = []
    for i, (subj, pred, objs) in enumerate(topics):
        for j, obj in enumerate(objs):
            quality = round(rng.uniform(0.3, 0.9), 2)
            text = f"{subj} {pred} is {obj}"
            evidence.append(make_evidence(i * 10 + j, text, quality))

    return evidence


def citation_bundle_json(evidence: list[dict]) -> dict:
    return {
        "summary": "Synthetic data for URA testing",
        "citations": [],
        "evidence": evidence,
    }


def citation_bundle_object(evidence: list[dict]):
    """Retorna un CitationBundle listo para usar."""
    from motor.core.web.citation.citation import CitationBundle, Evidence as EvidenceObj
    ev_objs = [EvidenceObj(**ev) for ev in evidence]
    return CitationBundle(summary="Synthetic data", citations=[], evidence=ev_objs)


def generate_benchmark_suite(base_dir: str = "/tmp/ura_benchmark_data") -> dict:
    """Genera datasets de diferentes tamaños para benchmarks."""
    sizes = {"10": 10, "100": 100, "1000": 1000, "10000": 10000}
    results = {}

    os.makedirs(base_dir, exist_ok=True)
    for label, n in sizes.items():
        path = os.path.join(base_dir, f"knowledge_{label}.json")
        ev = knowledge_domain(n)
        with open(path, "w") as f:
            json.dump(citation_bundle_json(ev), f)
        results[label] = {"path": path, "count": len(ev)}
        print(f"  {label}: {len(ev)} evidencias -> {path}")

    # Dataset de conflictos
    conflict_path = os.path.join(base_dir, "conflicts.json")
    ev = conflict_domain()
    with open(conflict_path, "w") as f:
        json.dump(citation_bundle_json(ev), f)
    results["conflicts"] = {"path": conflict_path, "count": len(ev)}

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="URA Synthetic Data Generator")
    parser.add_argument("--output", "-o", default="/tmp/ura_synthetic.json",
                        help="Output file path (JSON)")
    parser.add_argument("--domain", "-d", choices=["knowledge", "financial", "conflict", "all"],
                        default="knowledge", help="Domain of synthetic data")
    parser.add_argument("--count", "-n", type=int, default=10,
                        help="Number of evidence items")
    parser.add_argument("--benchmark", "-b", action="store_true",
                        help="Generate benchmark datasets (ignores --count)")
    parser.add_argument("--run-pipeline", "-r", action="store_true",
                        help="Run pipeline with generated data (requires all modules)")

    args = parser.parse_args()

    if args.benchmark:
        print("Generando datasets de benchmark...")
        results = generate_benchmark_suite()
        print(f"  Total: {sum(r['count'] for r in results.values())} evidencias en {len(results)} archivos")
        sys.exit(0)

    # Generar datos según dominio
    domain_map = {
        "knowledge": knowledge_domain,
        "financial": financial_domain,
        "conflict": conflict_domain,
    }

    if args.domain == "all":
        all_evidence = []
        for fn in domain_map.values():
            all_evidence.extend(fn(args.count))
        evidence = all_evidence
    else:
        evidence = domain_map[args.domain](args.count)

    # Guardar a JSON
    data = citation_bundle_json(evidence)
    with open(args.output, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Generadas {len(evidence)} evidencias -> {args.output}")

    # Ejecutar pipeline si se solicita
    if args.run_pipeline:
        print("Ejecutando pipeline con datos generados...")
        from motor.core.fusion.engine import FusionPipeline
        from motor.core.fusion.stages import (
            ExtractionStage, NormalizationStage, KnowledgeMergerStage,
            MemoryCandidateSelectionStage,
        )

        bundle = citation_bundle_object(evidence)
        pipeline = FusionPipeline(stages=[
            ExtractionStage(), NormalizationStage(),
            KnowledgeMergerStage(), MemoryCandidateSelectionStage(),
        ])

        from motor.memory import Memory
        import tempfile
        tmpdir = tempfile.mkdtemp(prefix="ura_synth_")
        snap = os.path.join(tmpdir, "snap.json")
        journal = os.path.join(tmpdir, "journal.jsonl")
        memory = Memory(snapshot_path=snap, journal_path=journal)

        from motor.core.fusion.models import FusionContext
        ctx = FusionContext(bundle=bundle)
        ctx.statistics["_memory_instance"] = memory

        import time
        t0 = time.perf_counter()
        for stage in pipeline._stages:
            ctx = stage.execute(ctx)
        t = time.perf_counter() - t0

        print(f"  Facts: {len(ctx.facts)} | Memoria: {memory.timeline.size} | Tiempo: {t*1000:.1f}ms")
        memory.close()

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
