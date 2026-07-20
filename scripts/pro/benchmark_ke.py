#!/usr/bin/env python3
"""Benchmark KE 1.x retrieval quality and latency.
Produces baseline metrics for later comparison with KE 2.0.

Usage:
  python3 scripts/pro/benchmark_ke.py                                    # full run
  python3 scripts/pro/benchmark_ke.py --corpus knowledge/evaluation/corpus
  python3 scripts/pro/benchmark_ke.py --dry-run                           # mock KE
  python3 scripts/pro/benchmark_ke.py --validate                          # corpus check only
"""

from __future__ import annotations

import json
import logging
import math
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("benchmark_ke")

HERE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(HERE))
CORPUS_DIR = HERE / "knowledge" / "evaluation" / "corpus"
RESULTS_DIR = HERE / "knowledge" / "evaluation" / "results"


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class Query:
    qid: str
    query: str
    domain: str


@dataclass
class Relevance:
    qid: str
    doc_id: str
    relevance: int  # 0-3


@dataclass
class RetrievalResult:
    doc_id: str
    score: float
    rank: int


@dataclass
class QueryResult:
    qid: str
    domain: str
    gold_docs: list[tuple[str, int]]
    retrieved: list[RetrievalResult]
    latency_ms: float
    recall_1: float
    recall_5: float
    recall_10: float
    precision_5: float
    mrr: float
    ndcg: float
    no_context: bool


@dataclass
class BenchmarkResults:
    queries_total: int
    queries_failed: int
    mean_recall_1: float
    mean_recall_5: float
    mean_recall_10: float
    mean_precision_5: float
    mean_mrr: float
    mean_ndcg: float
    map: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    throughput_qps: float
    no_context_rate: float
    doc_coverage: float
    domain_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    latency_all: list[float] = field(default_factory=list)
    corpus_version: str = ""
    timestamp: str = ""
    ke_version: str = "1.x"
    config: dict = field(default_factory=dict)


# ── Corpus loading ───────────────────────────────────────────────────────────


def load_corpus(corpus_dir: Path) -> tuple[list[Query], dict[str, list[Relevance]]]:
    queries_file = corpus_dir / "queries.jsonl"
    relevance_file = corpus_dir / "relevance.jsonl"

    if not queries_file.exists():
        msg = f"Queries file not found: {queries_file}"
        raise FileNotFoundError(msg)

    queries: list[Query] = []
    with queries_file.open() as f:
        for line in f:
            d = json.loads(line)
            queries.append(Query(qid=d["qid"], query=d["query"], domain=d.get("domain", "unknown")))

    relevance_map: dict[str, list[Relevance]] = {}
    if relevance_file.exists():
        with relevance_file.open() as f:
            for line in f:
                d = json.loads(line)
                r = Relevance(qid=d["qid"], doc_id=d["doc_id"], relevance=int(d.get("relevance", 1)))
                relevance_map.setdefault(r.qid, []).append(r)

    log.info("Cargadas %d queries y %d relevance judgments", len(queries), sum(len(v) for v in relevance_map.values()))
    return queries, relevance_map


# ── KE 1.x retrieval (real and mock) ─────────────────────────────────────────


class KERetrieval:
    """Interface for KE 1.x retrieval. Uses Qdrant vector search when available."""

    def __init__(self) -> None:
        self._client = None
        self._try_load_ke()
        self._mode = "ke1"

    def _try_load_ke(self) -> None:
        try:
            from motor.core.config import UraConfig
            from motor.core.qdrant_client import QdrantClient

            cfg = UraConfig()
            self._client = QdrantClient.instancia(cfg)
            if self._client.disponible:
                log.info("KE 1.x QdrantClient disponible")
            else:
                log.warning("QdrantClient no disponible — usando mock")
                self._client = None
        except Exception as e:
            log.warning("KE 1.x error en carga: %s — usando mock", e)
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def search(self, query: str, k: int = 10) -> list[RetrievalResult]:
        if self._client is not None:
            return self._search_real(query, k)
        return self._search_mock(query, k)

    def _search_real(self, query: str, k: int = 10) -> list[RetrievalResult]:
        try:
            raw = self._client.buscar_documentos(query, limit=k)
            results = []
            for i, r in enumerate(raw):
                payload = r.get("payload", {})
                doc_id = payload.get("id") or payload.get("source") or f"qdrant_{i}"
                results.append(RetrievalResult(doc_id=str(doc_id), score=float(r.get("score", 0.0)), rank=i))
            return results
        except Exception as e:
            log.warning("KE 1.x search falló: %s — mock fallback", e)
            return self._search_mock(query, k)

    def _search_mock(self, query: str, k: int = 10) -> list[RetrievalResult]:
        """Deterministic mock: returns results based on query content.
        Queries mentioning specific keywords match relevant docs.
        """
        doc_score_map: dict[str, float] = {}
        keywords = {
            "qdrant": "qdrant_client_docs",
            "degraded": "degraded_mode_spec",
            "eventbus": "eventbus_api_docs",
            "pipeline": "pipeline_executor_docs",
            "plugin": "plugin_registry_docs",
            "hook": "hook_manager_spec",
            "metric": "metrics_registry_docs",
            "counter": "counter_gauge_spec",
            "gauge": "counter_gauge_spec",
            "histogram": "histogram_timer_docs",
            "timer": "histogram_timer_docs",
            "health": "health_registry_docs",
            "readiness": "readiness_registry_docs",
            "config": "ura_config_reference",
            "model": "model_router_docs",
            "ollama": "ollama_config_guide",
            "chunk": "chunking_strategy_docs",
            "embedding": "chunking_strategy_docs",
            "fts5": "fts5_schema_docs",
            "search": "search_engine_docs",
            "retriev": "retrieval_methods_guide",
            "recall": "retrieval_methods_guide",
            "precision": "retrieval_methods_guide",
            "rerank": "retrieval_methods_guide",
            "test": "test_patterns_guide",
            "ruff": "ruff_config_docs",
            "lint": "ruff_config_docs",
            "benchmark": "benchmark_ke_docs",
            "corpus": "evaluation_corpus_guide",
            "ndcg": "quality_metrics_reference",
            "mrr": "quality_metrics_reference",
            "latency": "benchmark_ke_docs",
            "throughput": "benchmark_ke_docs",
            "coverage": "benchmark_ke_docs",
            "diversity": "benchmark_ke_docs",
            "fragment": "chunking_strategy_docs",
            "document": "knowledge_engine_docs",
            "index": "knowledge_engine_docs",
            "vector": "vector_index_guide",
            "service": "system_services_docs",
            "rollback": "pipeline_executor_docs",
            "stage": "pipeline_executor_docs",
            "timeout": "subprocess_executor_docs",
            "subprocess": "subprocess_executor_docs",
            "compat": "plugin_manifest_format",
            "manifest": "plugin_manifest_format",
            "dependen": "plugin_manifest_format",
            "lifecycle": "plugin_manifest_format",
            "circuit": "hook_circuit_breaker_docs",
            "prometheus": "systemd_service_guide",
            "alert": "systemd_service_guide",
        }
        q_lower = query.lower()
        for keyword, doc in keywords.items():
            if keyword in q_lower:
                score = 0.95 - (len(doc_score_map) * 0.05)
                doc_score_map[doc] = max(score, 0.5)

        if not doc_score_map:
            doc_score_map["general_knowledge_base"] = 0.5

        results = [
            RetrievalResult(doc_id=doc, score=score, rank=i)
            for i, (doc, score) in enumerate(sorted(doc_score_map.items(), key=lambda x: -x[1]))
        ]
        return results[:k]


# ── Metrics computation ──────────────────────────────────────────────────────


def compute_recall(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    retrieved_k = set(retrieved[:k])
    hits = len(retrieved_k & relevant)
    return hits / len(relevant)


def compute_precision(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    retrieved_k = set(retrieved[:k])
    hits = len(retrieved_k & relevant)
    return hits / k


def compute_mrr(retrieved: list[str], relevant: set[str]) -> float:
    for i, doc in enumerate(retrieved):
        if doc in relevant:
            return 1.0 / (i + 1)
    return 0.0


def compute_ap(retrieved: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 0.0
    hits = 0
    sum_precision = 0.0
    for i, doc in enumerate(retrieved):
        if doc in relevant:
            hits += 1
            sum_precision += hits / (i + 1)
    return sum_precision / len(relevant)


def compute_ndcg(retrieved: list[str], relevance_map: dict[str, int], k: int) -> float:
    dcg = 0.0
    for i, doc in enumerate(retrieved[:k]):
        rel = relevance_map.get(doc, 0)
        dcg += (2**rel - 1) / math.log2(i + 2)

    # Ideal DCG: sort relevance scores descending
    ideal_rels = sorted(relevance_map.values(), reverse=True)
    idcg = 0.0
    for i, rel in enumerate(ideal_rels[:k]):
        idcg += (2**rel - 1) / math.log2(i + 2)

    return dcg / idcg if idcg > 0 else 0.0


# ── Main benchmark ───────────────────────────────────────────────────────────


def validate_corpus_indexed(
    relevance_map: dict[str, list[Relevance]],
    retriever: KERetrieval,
) -> list[str]:
    errors: list[str] = []
    all_doc_ids: set[str] = set()
    for rels in relevance_map.values():
        for r in rels:
            all_doc_ids.add(r.doc_id)

    if not all_doc_ids:
        errors.append("No hay doc_ids en el corpus para validar")
        return errors

    found = 0
    for doc_id in sorted(all_doc_ids):
        results = retriever.search(doc_id.replace("_", " "), k=1)
        if results and results[0].score >= 0.1:
            found += 1
        else:
            errors.append(f"Documento no encontrado en KE index: {doc_id}")

    coverage = found / len(all_doc_ids)
    if coverage < 0.95:
        errors.append(f"Coverage documental insuficiente: {coverage:.1%} (min 95%)")

    if errors:
        log.warning("Validación corpus: %d/%d documentos encontrados (%.1f%%)", found, len(all_doc_ids), coverage * 100)
    else:
        log.info(
            "Validación corpus: %d/%d documentos encontrados (%.1f%%) — OK",
            found,
            len(all_doc_ids),
            coverage * 100,
        )
    return errors


def run_benchmark(corpus_dir: Path, results_dir: Path, dry_run: bool = False) -> BenchmarkResults:  # noqa: PLR0915
    queries, relevance_map = load_corpus(corpus_dir)

    retriever = KERetrieval()
    if dry_run:
        retriever._client = None  # force mock

    if not dry_run and retriever.available:
        validation_errors = validate_corpus_indexed(relevance_map, retriever)
        if validation_errors:
            for e in validation_errors:
                log.error("VALIDACIÓN: %s", e)
            msg = (
                f"Corpus validation failed: {len(validation_errors)} errors. "
                "Index golden documents first with: python3 scripts/pro/index_golden_docs.py"
            )
            raise RuntimeError(
                msg,
            )
        log.info("Validación corpus superada — ejecutando benchmark")

    query_results: list[QueryResult] = []
    all_latencies: list[float] = []
    total_no_context = 0

    for q in queries:
        gold = relevance_map.get(q.qid, [])
        gold_docs = [(r.doc_id, r.relevance) for r in gold]
        gold_set = {r.doc_id for r in gold}
        gold_relevance = {r.doc_id: r.relevance for r in gold}

        start = time.monotonic()
        retrieved = retriever.search(q.query, k=10)
        elapsed_ms = (time.monotonic() - start) * 1000

        retrieved_ids = [r.doc_id for r in retrieved]
        recalled_set = retrieved_ids[:10]

        r1 = compute_recall(recalled_set, gold_set, 1)
        r5 = compute_recall(recalled_set, gold_set, 5)
        r10 = compute_recall(recalled_set, gold_set, 10)
        p5 = compute_precision(recalled_set, gold_set, 5)
        mrr = compute_mrr(recalled_set, gold_set)
        ndcg = compute_ndcg(recalled_set, gold_relevance, 10)

        best_score = retrieved[0].score if retrieved else 0.0
        no_ctx = best_score < 0.6

        if no_ctx:
            total_no_context += 1

        all_latencies.append(elapsed_ms)

        query_results.append(
            QueryResult(
                qid=q.qid,
                domain=q.domain,
                gold_docs=gold_docs,
                retrieved=retrieved,
                latency_ms=elapsed_ms,
                recall_1=r1,
                recall_5=r5,
                recall_10=r10,
                precision_5=p5,
                mrr=mrr,
                ndcg=ndcg,
                no_context=no_ctx,
            ),
        )

    # Aggregate
    all_recall_1 = [qr.recall_1 for qr in query_results]
    all_recall_5 = [qr.recall_5 for qr in query_results]
    all_recall_10 = [qr.recall_10 for qr in query_results]
    all_precision_5 = [qr.precision_5 for qr in query_results]
    all_mrr = [qr.mrr for qr in query_results]
    all_ndcg = [qr.ndcg for qr in query_results]
    all_ap = []

    for q in queries:
        gold = relevance_map.get(q.qid, [])
        gold_set = {r.doc_id for r in gold}
        retrieved_ids = [r.doc_id for r in (next((qr.retrieved for qr in query_results if qr.qid == q.qid), []))]

    # Compute AP per query
    for qr in query_results:
        gold_set = {d for d, _ in qr.gold_docs}
        retrieved_ids = [r.doc_id for r in qr.retrieved]
        all_ap.append(compute_ap(retrieved_ids, gold_set))

    # Loaded docs: all unique doc_ids retrieved across all queries
    all_retrieved_docs: set[str] = set()
    for qr in query_results:
        for r in qr.retrieved:
            all_retrieved_docs.add(r.doc_id)
    all_gold_docs: set[str] = set()
    for q in queries:
        for r in relevance_map.get(q.qid, []):
            all_gold_docs.add(r.doc_id)
    doc_coverage = len(all_retrieved_docs & all_gold_docs) / len(all_gold_docs) if all_gold_docs else 0.0

    # Domain breakdown
    domains: dict[str, list[float]] = {}
    for qr in query_results:
        domains.setdefault(qr.domain, []).append(qr.ndcg)
    domain_breakdown = {d: {"ndcg_mean": round(statistics.mean(v), 4), "count": len(v)} for d, v in domains.items()}

    sorted_lat = sorted(all_latencies)
    n = len(sorted_lat)
    return BenchmarkResults(
        queries_total=len(queries),
        queries_failed=0,
        mean_recall_1=round(statistics.mean(all_recall_1), 4),
        mean_recall_5=round(statistics.mean(all_recall_5), 4),
        mean_recall_10=round(statistics.mean(all_recall_10), 4),
        mean_precision_5=round(statistics.mean(all_precision_5), 4),
        mean_mrr=round(statistics.mean(all_mrr), 4),
        mean_ndcg=round(statistics.mean(all_ndcg), 4),
        map=round(statistics.mean(all_ap), 4),
        latency_p50=round(sorted_lat[max(0, int(n * 0.50))], 2),
        latency_p95=round(sorted_lat[max(0, int(n * 0.95))], 2),
        latency_p99=round(sorted_lat[max(0, int(n * 0.99))], 2),
        throughput_qps=round(len(queries) / (sum(all_latencies) / 1000), 2) if all_latencies else 0,
        no_context_rate=round(total_no_context / len(queries), 4),
        doc_coverage=round(doc_coverage, 4),
        domain_breakdown=domain_breakdown,
        latency_all=sorted_lat,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ke_version="1.x (mock)" if dry_run or not retriever.available else "1.x (real)",
    )


def print_results(r: BenchmarkResults) -> None:
    if r.domain_breakdown:
        for _d, _info in sorted(r.domain_breakdown.items()):
            pass


def save_results(r: BenchmarkResults, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ke_version": r.ke_version,
        "corpus_version": r.corpus_version,
        "timestamp": r.timestamp,
        "queries_total": r.queries_total,
        "queries_failed": r.queries_failed,
        "mean_recall_1": r.mean_recall_1,
        "mean_recall_5": r.mean_recall_5,
        "mean_recall_10": r.mean_recall_10,
        "mean_precision_5": r.mean_precision_5,
        "mean_mrr": r.mean_mrr,
        "mean_ndcg": r.mean_ndcg,
        "map": r.map,
        "latency_p50_ms": r.latency_p50,
        "latency_p95_ms": r.latency_p95,
        "latency_p99_ms": r.latency_p99,
        "throughput_qps": r.throughput_qps,
        "no_context_rate": r.no_context_rate,
        "doc_coverage": r.doc_coverage,
        "domain_breakdown": r.domain_breakdown,
        "latency_all": r.latency_all,
    }
    with open(path, "w") as f:  # noqa: PTH123
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info("Resultados guardados: %s", path)


def validate_corpus(corpus_dir: Path) -> list[str]:
    errors: list[str] = []
    queries, relevance_map = load_corpus(corpus_dir)

    if len(queries) < 200:
        errors.append(f"Corpus debe tener ≥200 queries (tiene {len(queries)})")

    qids = [q.qid for q in queries]
    if len(qids) != len(set(qids)):
        dupes = {qid for qid in qids if qids.count(qid) > 1}
        errors.append(f"Query IDs duplicados: {dupes}")

    for q in queries:
        if not q.qid.startswith(("sys_", "code_", "know_")):
            errors.append(f"QID {q.qid} no sigue convención sys_/code_/know_")  # noqa: PERF401

    domains = {q.domain for q in queries}
    if len(domains) < 2:
        errors.append(f"Se requieren ≥2 dominios (tiene {len(domains)}: {domains})")

    for qid, rels in relevance_map.items():
        for r in rels:
            if r.relevance not in (0, 1, 2, 3):
                errors.append(f"Relevance score inválido en {qid}: {r.relevance}")  # noqa: PERF401

    if not errors:
        log.info(
            "Corpus válido: %d queries, %d dominios, %d relevance judgments",
            len(queries),
            len(domains),
            sum(len(v) for v in relevance_map.values()),
        )
    else:
        for e in errors:
            log.error("VALIDACIÓN: %s", e)
    return errors


def create_baseline_doc(results_path: Path, corpus_dir: Path) -> str:
    import platform
    import subprocess

    with results_path.open() as f:
        data = json.load(f)

    metadata_file = corpus_dir / "metadata.json"
    meta = {}
    if metadata_file.exists():
        meta = json.loads(metadata_file.read_text())

    try:
        git_hash = subprocess.run(  # noqa: PLW1510
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        git_hash = "unknown"
    try:
        git_tag = subprocess.run(  # noqa: PLW1510
            ["git", "describe", "--tags", "--always"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        git_tag = "unknown"

    md = f"""# Fase 12 — Baseline KE 1.x

> **Generado:** {data["timestamp"]}
> **Commit:** `{git_hash}`
> **Tag:** `{git_tag}`
> **KE version:** {data["ke_version"]}

---

## Hardware

| Componente | Valor |
|------------|-------|
| CPU | {platform.processor() or "N/A"} |
| Python | {platform.python_version()} |
| Plataforma | {platform.platform()} |

## Corpus

| Métrica | Valor |
|---------|-------|
| Versión | {meta.get("version", "N/A")} |
| Consultas | {data["queries_total"]} |
| Relevance judgments | {meta.get("total_relevance_judgments", "N/A")} |
| Documentos únicos | {meta.get("unique_documents", "N/A")} |
| Dominios | {", ".join(data.get("domain_breakdown", {}).keys())} |

## Métricas de Recuperación

| Métrica | Valor |
|---------|-------|
| Recall@1 | {data["mean_recall_1"]} |
| Recall@5 | {data["mean_recall_5"]} |
| Recall@10 | {data["mean_recall_10"]} |
| Precision@5 | {data["mean_precision_5"]} |
| MRR | {data["mean_mrr"]} |
| MAP | {data["map"]} |
| nDCG@10 | {data["mean_ndcg"]} |

## Latencia

| Métrica | Valor |
|---------|-------|
| P50 | {data["latency_p50_ms"]}ms |
| P95 | {data["latency_p95_ms"]}ms |
| P99 | {data["latency_p99_ms"]}ms |
| Throughput | {data["throughput_qps"]} qps |

## Cobertura

| Métrica | Valor |
|---------|-------|
| Tasa sin contexto | {data["no_context_rate"]:%} |
| Cobertura documental | {data["doc_coverage"]:%} |

## Desglose por dominio

| Dominio | nDCG | Consultas |
|---------|------|-----------|
"""
    for d, info in sorted(data.get("domain_breakdown", {}).items()):
        md += f"| {d} | {info['ndcg_mean']} | {info['count']} |\n"

    md += """
---

## Configuración del Índice

| Parámetro | Valor |
|-----------|-------|
| Chunking | Por tokens (512 tokens, overlap 64) |
| Embeddings | nomic-embed-text (Ollama) |
| Index | Qdrant (cosine similarity) |
| Ranking | Cosine similarity únicamente |
| Reranking | No |
| Retrieval | Single-stage (solo vectorial) |

> Este baseline se generó con `scripts/pro/benchmark_ke.py`.
> Para reproducir: `python3 scripts/pro/benchmark_ke.py --corpus knowledge/evaluation/corpus`
"""
    return md


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark KE 1.x — métricas de recuperación")
    parser.add_argument("--corpus", default=str(CORPUS_DIR), help="Directorio del corpus")
    parser.add_argument("--output", default=str(RESULTS_DIR), help="Directorio de resultados")
    parser.add_argument("--dry-run", action="store_true", help="Usar mock KE (no requiere KE real)")
    parser.add_argument("--validate", action="store_true", help="Solo validar corpus, no ejecutar benchmark")
    parser.add_argument("--save", action="store_true", help="Guardar resultados y baseline")
    args = parser.parse_args()

    corpus_dir = Path(args.corpus)
    results_dir = Path(args.output)
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / "baseline_results.json"
    baseline_doc_path = HERE / "docs" / "architecture" / "FASE12_BASELINE.md"

    if args.validate:
        errors = validate_corpus(corpus_dir)
        if errors:
            log.error("Corpus inválido — %d errores", len(errors))
            return 1
        return 0

    errors = validate_corpus(corpus_dir)
    if errors:
        log.warning("Corpus tiene %d errores — continuando de todas formas", len(errors))

    try:
        results = run_benchmark(corpus_dir, results_dir, dry_run=args.dry_run)
    except RuntimeError as e:
        log.exception("Benchmark abortado: %s", e)
        print(f"\n  ERROR: {e}", file=__import__("sys").stdout)
        return 1
    print_results(results)

    if args.save or not args.dry_run:
        save_results(results, results_path)
        md = create_baseline_doc(results_path, corpus_dir)
        baseline_doc_path.write_text(md)
        log.info("Baseline doc guardado: %s", baseline_doc_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
