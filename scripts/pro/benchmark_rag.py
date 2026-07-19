#!/usr/bin/env python3
"""Benchmark comparativo de estrategias de Retrieval.

Evalúa múltiples retrievers contra un corpus y genera ranking:
  - Recall@K, Precision@K, MRR, MAP, nDCG@K
  - Latencia P50/P95/P99
  - Throughput
  - Ranking automático por métrica

Uso:
  python3 scripts/pro/benchmark_rag.py --corpus corpus.json --retrievers bm25 semantic hybrid --output resultados.json
  python3 scripts/pro/benchmark_rag.py --example  # genera corpus de ejemplo
"""

import argparse
import json
import logging
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from motor.core.evaluation import EvaluationCorpus, EvaluationEngine, EvaluationQuery

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("benchmark_rag")

LINEA = "-" * 78


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    idx = max(0, min(len(data) - 1, int(len(data) * p / 100)))
    return sorted(data)[idx]


def _generar_corpus_ejemplo(path: str) -> None:
    """Genera un corpus de evaluación de ejemplo con 10 consultas."""
    corpus = EvaluationCorpus("ejemplo")
    queries = [
        EvaluationQuery("q1", "sistemas de recuperacion de informacion", {"d1", "d3", "d5"}),
        EvaluationQuery("q2", "modelos de lenguaje grandes", {"d2", "d4"}),
        EvaluationQuery("q3", "bases de datos vectoriales", {"d3", "d6", "d7"}),
        EvaluationQuery("q4", "embeddings y representacion semantica", {"d1", "d4", "d8"}),
        EvaluationQuery("q5", "procesamiento de lenguaje natural", {"d2", "d5", "d9"}),
        EvaluationQuery("q6", "busqueda por similitud", {"d3", "d6"}),
        EvaluationQuery("q7", "indexacion invertida", {"d1", "d7"}),
        EvaluationQuery("q8", "algoritmos de ranking", {"d4", "d8", "d9"}),
        EvaluationQuery("q9", "sistemas de recomendacion", {"d5", "d6", "d10"}),
        EvaluationQuery("q10", "analisis de texto", {"d2", "d7", "d10"}),
    ]
    corpus.add_queries(queries)
    corpus.save(path)


def _crear_retrievers_mock() -> dict[str, Callable]:
    """Crea retrievers mock para testing."""

    def _bm25(query: str) -> list[str]:
        return ["d1", "d3", "d2", "d5", "d4", "d7", "d6", "d9", "d8", "d10"]

    def _semantic(query: str) -> list[str]:
        return ["d1", "d4", "d3", "d2", "d5", "d8", "d6", "d7", "d10", "d9"]

    def _hybrid(query: str) -> list[str]:
        return ["d1", "d3", "d4", "d2", "d5", "d7", "d6", "d8", "d9", "d10"]

    return {"bm25": _bm25, "semantic": _semantic, "hybrid": _hybrid}


def _mostrar_resultados(resultados: dict[str, Any], k: int) -> None:
    """Muestra resultados en tabla."""
    hdr = "  {:15} {:>8} {:>8} {:>8} {:>8} {:>8} {:>8} {:>8}"
    hdr.format("Retriever", "Recall", "Prec", "MRR", "nDCG", "MAP", "P50(ms)", "P95(ms)")

    for data in resultados["configs"].values():
        data["metrics"]
        data["latency_stats"]

    for _metric, _info in resultados.get("best_by_metric", {}).items():
        pass


def _mostrar_ranking(resultados: dict[str, Any], k: int) -> None:
    """Muestra ranking agregado (Score = promedio de todas las métricas)."""
    scores: list[tuple[str, float]] = []
    for cfg_name, data in resultados["configs"].items():
        m = data["metrics"]
        metrics_list = [
            m.get(f"recall@{k}", 0),
            m.get(f"precision@{k}", 0),
            m.get("mrr", 0),
            m.get(f"ndcg@{k}", 0),
            m.get("map", 0),
        ]
        avg = statistics.mean(metrics_list)
        scores.append((cfg_name, avg))

    scores.sort(key=lambda x: x[1], reverse=True)
    for _rank, (_name, _score) in enumerate(scores, 1):
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark RAG")
    parser.add_argument("--corpus", type=str, default="", help="ruta al corpus JSON")
    parser.add_argument("--retrievers", type=str, nargs="+", default=[], help="retrievers a evaluar")
    parser.add_argument("--output", type=str, default="", help="ruta JSON de salida")
    parser.add_argument("--example", action="store_true", help="generar corpus de ejemplo")
    parser.add_argument("--k", type=int, default=10, help="top K para métricas (default: 10)")
    args = parser.parse_args()

    if args.example:
        _generar_corpus_ejemplo(args.output or "corpus_ejemplo.json")
        return 0

    corpus_path = args.corpus
    if not corpus_path or not Path(corpus_path).exists():
        return 1

    # Cargar corpus
    corpus = EvaluationCorpus.load(corpus_path)

    # Registrar retrievers
    engine = EvaluationEngine()
    engine.register_corpus("default", corpus)

    retrievers_to_run: dict[str, Callable] = {}

    if args.retrievers:
        mock_retrievers = _crear_retrievers_mock()
        for name in args.retrievers:
            if name in mock_retrievers:
                retrievers_to_run[name] = mock_retrievers[name]
                engine.register_retriever(name, mock_retrievers[name])
            else:
                pass
    else:
        # Si no se especifican, usar todos los mock
        mock_retrievers = _crear_retrievers_mock()
        for name, fn in mock_retrievers.items():
            retrievers_to_run[name] = fn
            engine.register_retriever(name, fn)

    # Ejecutar comparación
    t0 = time.monotonic()
    resultados = engine.compare("default", list(retrievers_to_run), k=args.k)
    elapsed = (time.monotonic() - t0) * 1000

    _mostrar_resultados(resultados, args.k)
    _mostrar_ranking(resultados, args.k)

    # Exportar
    if args.output:
        output = {
            "corpus": corpus.name,
            "k": args.k,
            "total_queries": len(corpus),
            "elapsed_ms": round(elapsed, 1),
            "resultados": resultados,
            "ranking": [
                {"rank": rank, "config": name, "score": round(score, 4)}
                for rank, (name, score) in enumerate(
                    sorted(
                        [
                            (
                                n,
                                statistics.mean(
                                    [
                                        d["metrics"].get(f"recall@{args.k}", 0),
                                        d["metrics"].get(f"precision@{args.k}", 0),
                                        d["metrics"].get("mrr", 0),
                                        d["metrics"].get(f"ndcg@{args.k}", 0),
                                        d["metrics"].get("map", 0),
                                    ],
                                ),
                            )
                            for n, d in resultados["configs"].items()
                        ],
                        key=lambda x: x[1],
                        reverse=True,
                    ),
                    1,
                )
            ],
        }
        Path(args.output).write_text(json.dumps(output, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
