#!/usr/bin/env python3
"""Benchmark F24 — Web Intelligence end-to-end.

Mide latencias por etapa, throughput, compresión y trazabilidad.
Sin acceso a Internet. Resultados exportados a docs/architecture/benchmark_f24.json
y docs/architecture/benchmark_f24_pipeline.json.

Uso:
    python3 scripts/pro/benchmark_f24.py [--iterations 5]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from statistics import mean, stdev
from typing import Any

# ── Asegurar PYTHONPATH ──────────────────────
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from motor.core.web.citation.citation import CitationEngine
from motor.core.web.cleaner.cleaner import DocumentCleaner
from motor.core.web.cleaner.deduplication import DeduplicationEngine
from motor.core.web.extractor.providers.html_extractor import HtmlExtractor
from motor.core.web.ranker.ranker import DocumentRanker
from motor.core.web.summarizer.summarizer import ExtractiveSummarizer

# ── Datos de prueba ─────────────────────────

HTML_PYTHON = """<html><head>
<title>Python Guide</title>
<meta name="description" content="Complete Python programming guide">
</head><body>
<p>Python is a high-level programming language. It was created by Guido van Rossum.
Python emphasizes code readability. It is widely used in web development.
Many developers prefer Python for data science and machine learning.
Python has a large standard library. The language supports multiple paradigms.
Python's design philosophy emphasizes code readability and simplicity.</p>
</body></html>"""

HTML_JAVA = """<html><head>
<title>Java Programming</title>
<meta name="description" content="Java programming language overview">
</head><body>
<p>Java is a class-based programming language. It is designed for portability.
Java runs on billions of devices worldwide. The language is used for enterprise.
Android development uses Java extensively. Java has strong typing and GC.</p>
</body></html>"""

HTML_GO = """<html><head>
<title>Go Language</title>
</head><body>
<p>Go is a compiled language developed by Google. It has built-in concurrency.
Go is known for its simplicity and performance. Many cloud tools use Go.</p>
</body></html>"""

HTML_RUST = """<html><head>
<title>Rust Programming</title>
</head><body>
<p>Rust is a systems language focused on safety. It prevents memory errors.
Rust is used for performance-critical applications. Mozilla created Rust.</p>
</body></html>"""

HTML_EMPTY = """<html><head><title>Empty</title></head><body></body></html>"""

HTML_DUP = """<html><head>
<title>Python Guide</title>
<meta name="description" content="Complete Python programming guide">
</head><body>
<p>Python is a high-level programming language. It was created by Guido van Rossum.
Python emphasizes code readability. It is widely used in web development.</p>
</body></html>"""

DOCS_RAW = [
    ("http://example.com/python", HTML_PYTHON),
    ("http://example.com/java", HTML_JAVA),
    ("http://example.com/go", HTML_GO),
    ("http://example.com/rust", HTML_RUST),
    ("http://example.com/empty", HTML_EMPTY),
    ("http://example.com/python-dup", HTML_DUP),
    ("http://example.com/python-alt", HTML_PYTHON),
]

QUERY = "python programming"
MAX_SUMMARY = 8
WARMUP = 2


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    idx = math.ceil(p * len(data)) - 1
    return sorted(data)[max(0, min(idx, len(data) - 1))]


def compute_stats(times: list[float]) -> dict[str, float]:
    if len(times) < 2:
        return {
            "mean": round(mean(times), 2) if times else 0.0,
            "stddev": 0.0,
            "p50": round(percentile(times, 0.5), 2),
            "p95": round(percentile(times, 0.95), 2),
            "p99": round(percentile(times, 0.99), 2),
            "min": round(min(times), 2) if times else 0.0,
            "max": round(max(times), 2) if times else 0.0,
        }
    return {
        "mean": round(mean(times), 2),
        "stddev": round(stdev(times), 2),
        "p50": round(percentile(times, 0.5), 2),
        "p95": round(percentile(times, 0.95), 2),
        "p99": round(percentile(times, 0.99), 2),
        "min": round(min(times), 2),
        "max": round(max(times), 2),
    }


def run_pipeline(iterations: int = 5) -> dict[str, Any]:
    """Ejecuta el pipeline completo y retorna métricas."""
    times: dict[str, list[float]] = {
        "extract": [],
        "clean": [],
        "dedup": [],
        "rank": [],
        "summarize": [],
        "cite": [],
    }
    documents_in = len(DOCS_RAW)
    documents_valid = 0
    documents_removed = 0
    citations_count = 0
    evidence_count = 0
    summary_compression = 0.0

    extractor = HtmlExtractor()
    cleaner = DocumentCleaner(min_words=3)
    dedup = DeduplicationEngine()
    ranker = DocumentRanker()
    summarizer = ExtractiveSummarizer()
    cite_engine = CitationEngine()

    for _ in range(WARMUP + iterations):
        t0 = time.monotonic()
        # Extract
        docs: list = []
        for url, html in DOCS_RAW:
            docs.append(extractor.extract(html, url))
        t_extract = time.monotonic() - t0

        # Clean
        t1 = time.monotonic()
        cleaned = cleaner.clean(docs)
        t_clean = time.monotonic() - t1

        # Dedup
        t2 = time.monotonic()
        unique = dedup.deduplicate(cleaned.documents, stats=cleaned.stats)
        t_dedup = time.monotonic() - t2

        # Rank
        t3 = time.monotonic()
        ranker.rank(QUERY, unique)
        t_rank = time.monotonic() - t3

        # Summarize
        t4 = time.monotonic()
        summary = summarizer.summarize(unique, max_length=MAX_SUMMARY)
        t_summarize = time.monotonic() - t4

        # Cite
        t5 = time.monotonic()
        bundle = cite_engine.build(summary, unique)
        t_cite = time.monotonic() - t5

        # Solo registrar tiempos de las iteraciones reales (después de warmup)
        if _ >= WARMUP:
            times["extract"].append(t_extract * 1000)
            times["clean"].append(t_clean * 1000)
            times["dedup"].append(t_dedup * 1000)
            times["rank"].append(t_rank * 1000)
            times["summarize"].append(t_summarize * 1000)
            times["cite"].append(t_cite * 1000)

        documents_valid = len(unique)
        documents_removed = cleaned.stats.documents_removed
        citations_count = bundle.traceability_report["total_citations"]
        evidence_count = bundle.traceability_report["evidence_count"]
        summary_compression = summary.compression_ratio

    total_times = [
        times["extract"][i]
        + times["clean"][i]
        + times["dedup"][i]
        + times["rank"][i]
        + times["summarize"][i]
        + times["cite"][i]
        for i in range(len(times["extract"]))
    ]

    return {
        "meta": {
            "pipeline": "Web Intelligence F24",
            "iterations": iterations,
            "warmup": WARMUP,
            "documents_input": documents_in,
            "max_summary_sentences": MAX_SUMMARY,
            "query": QUERY,
        },
        "latency_ms": {
            stage: compute_stats(vals) for stage, vals in times.items()
        },
        "total_latency_ms": compute_stats(total_times),
        "throughput": {
            "docs_per_second": round(
                documents_in / (mean(total_times) / 1000) if total_times else 0, 1
            ),
            "total_time_seconds": round(mean(total_times) / 1000, 3),
        },
        "documents": {
            "total_input": documents_in,
            "valid_after_clean": documents_valid + documents_removed,
            "valid_after_dedup": documents_valid,
            "removed_total": documents_removed,
            "duplication_pct": cleaned.stats.duplication_pct,
        },
        "summary": {
            "sentences": len(summary.sentences),
            "compression_ratio": summary_compression,
        },
        "citations": {
            "total": citations_count,
            "unique_evidence": evidence_count,
        },
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    print(f"  📄 {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark F24 Web Intelligence")
    parser.add_argument(
        "--iterations", type=int, default=5, help="Número de iteraciones (default: 5)"
    )
    args = parser.parse_args()

    print(f"Benchmark F24 — {args.iterations} iteraciones (+{WARMUP} warmup)")
    print("-" * 50)

    result = run_pipeline(iterations=args.iterations)

    print(f"\nDocumentos: {result['documents']['total_input']} → {result['documents']['valid_after_dedup']}")
    print(f"Duplicados eliminados: {result['documents']['removed_total']} ({result['documents']['duplication_pct']}%)")
    print(f"Citas: {result['citations']['total']} (evidencia única: {result['citations']['unique_evidence']})")
    print(f"Compresión resumen: {result['summary']['compression_ratio']:.1%}")
    print(f"\nThroughput: {result['throughput']['docs_per_second']} docs/s")
    print(f"Tiempo total medio: {result['total_latency_ms']['mean']}ms")

    print("\nLatencia por etapa (ms):")
    print(f"  {'Etapa':<15} {'Media':>8} {'P50':>8} {'P95':>8} {'P99':>8}")
    print("  " + "-" * 47)
    for stage, stats in result["latency_ms"].items():
        print(
            f"  {stage:<15} {stats['mean']:>8.1f} {stats['p50']:>8.1f} {stats['p95']:>8.1f} {stats['p99']:>8.1f}"
        )

    out_dir = REPO / "docs" / "architecture"
    write_json(out_dir / "benchmark_f24.json", result)
    write_json(out_dir / "benchmark_f24_pipeline.json", {
        "pipeline_stages": list(result["latency_ms"].keys()),
        "iterations": args.iterations,
        "total_documents": result["documents"]["total_input"],
        "valid_documents": result["documents"]["valid_after_dedup"],
        "duplicates_removed": result["documents"]["removed_total"],
        "citations": result["citations"]["total"],
        "evidence": result["citations"]["unique_evidence"],
        "compression_ratio": result["summary"]["compression_ratio"],
        "throughput_docs_per_second": result["throughput"]["docs_per_second"],
        "total_time_ms_mean": result["total_latency_ms"]["mean"],
    })


if __name__ == "__main__":
    main()
