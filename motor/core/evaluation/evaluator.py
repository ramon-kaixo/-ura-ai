"""Motor de evaluación de Retrieval.

Evalúa configuraciones de retrieval contra corpus de evaluación.
Genera resultados persistibles en JSON.
Thread-safe. Independiente del pipeline RAG existente.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from motor.core.evaluation.corpus import EvaluationCorpus

from motor.core.evaluation.metrics import (
    map_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


class RetrievalResult:
    """Resultado de retrieval para una consulta."""

    __slots__ = ("latency_ms", "query_id", "retrieved")

    def __init__(self, query_id: str, retrieved: list[str], latency_ms: float = 0.0) -> None:
        self.query_id = query_id
        self.retrieved = retrieved
        self.latency_ms = latency_ms


class EvaluationRun:
    """Resultado de una ejecución de evaluación."""

    def __init__(
        self,
        corpus_name: str,
        config_name: str,
        metrics: dict[str, float],
        per_query: list[dict[str, Any]],
        timestamp: float,
        latency_stats: dict[str, float],
    ) -> None:
        self.corpus_name = corpus_name
        self.config_name = config_name
        self.metrics = metrics
        self.per_query = per_query
        self.timestamp = timestamp
        self.latency_stats = latency_stats

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus": self.corpus_name,
            "config": self.config_name,
            "metrics": self.metrics,
            "per_query": self.per_query,
            "timestamp": self.timestamp,
            "latency_stats": self.latency_stats,
        }


class EvaluationEngine:
    """Motor de evaluación de Retrieval.

    Uso:
        engine = EvaluationEngine()
        engine.register_corpus("test", corpus)
        engine.register_retriever("bm25", my_retrieve_fn)

        engine.evaluate("test", "bm25", k=10)
        engine.save_results("results.json")
    """

    def __init__(self) -> None:
        self._corpora: dict[str, EvaluationCorpus] = {}
        self._retrievers: dict[str, Callable] = {}
        self._results: list[EvaluationRun] = []
        self._max_results = 100

    def register_corpus(self, name: str, corpus: EvaluationCorpus) -> None:
        self._corpora[name] = corpus

    def register_retriever(self, name: str, retrieve_fn: Callable) -> None:
        self._retrievers[name] = retrieve_fn

    def list_corpora(self) -> list[str]:
        return list(self._corpora)

    def list_retrievers(self) -> list[str]:
        return list(self._retrievers)

    def evaluate(
        self,
        corpus_name: str,
        config_name: str,
        k: int = 10,
        relevance_scores: bool = False,  # noqa: FBT001, FBT002
    ) -> EvaluationRun:
        """Ejecuta evaluación de un config retrieval contra un corpus.

        Args:
            corpus_name: nombre del corpus registrado.
            config_name: nombre del retriever registrado.
            k: top K para métricas.
            relevance_scores: usar relevance_scores si disponibles.

        Returns:
            EvaluationRun con métricas agregadas.
        """
        corpus = self._corpora.get(corpus_name)
        if corpus is None:
            raise ValueError(f"Corpus not found: {corpus_name}")
        retrieve_fn = self._retrievers.get(config_name)
        if retrieve_fn is None:
            raise ValueError(f"Retriever not found: {config_name}")

        per_query: list[dict[str, Any]] = []
        latencies: list[float] = []
        query_pairs: list[tuple[set[str], list[str]]] = []

        for qid, query in corpus.queries.items():
            t0 = time.monotonic()
            retrieved = retrieve_fn(query.query_text)
            elapsed = (time.monotonic() - t0) * 1000

            latencies.append(elapsed)
            query_pairs.append((query.relevant_docs, retrieved))

            q_result: dict[str, Any] = {
                "query_id": qid,
                "query_text": query.query_text[:100],
                "recall": recall_at_k(query.relevant_docs, retrieved, k),
                "precision": precision_at_k(query.relevant_docs, retrieved, k),
                "mrr": mrr(query.relevant_docs, retrieved),
                "ndcg": ndcg_at_k(
                    query.relevant_docs, retrieved, k,
                    relevance_scores=query.relevance_scores if relevance_scores else None,
                ),
                "latency_ms": round(elapsed, 1),
            }
            per_query.append(q_result)

        nq = len(per_query) if per_query else 1
        aggregated: dict[str, float] = {
            f"recall@{k}": sum(q["recall"] for q in per_query) / nq,
            f"precision@{k}": sum(q["precision"] for q in per_query) / nq,
            "mrr": sum(q["mrr"] for q in per_query) / nq,
            f"ndcg@{k}": sum(q["ndcg"] for q in per_query) / nq,
            "map": map_at_k(query_pairs, k) if query_pairs else 0.0,
        }

        latency_stats = {
            "mean_ms": round(sum(latencies) / max(1, len(latencies)), 1),
            "min_ms": round(min(latencies), 1) if latencies else 0.0,
            "max_ms": round(max(latencies), 1) if latencies else 0.0,
        }

        run = EvaluationRun(
            corpus_name=corpus_name,
            config_name=config_name,
            metrics=aggregated,
            per_query=per_query,
            timestamp=time.time(),
            latency_stats=latency_stats,
        )

        self._results.append(run)
        if len(self._results) > self._max_results:
            self._results.pop(0)

        return run

    def compare(
        self,
        corpus_name: str,
        config_names: list[str],
        k: int = 10,
    ) -> dict[str, Any]:
        """Compara múltiples configs retrieval sobre el mismo corpus."""
        comparison: dict[str, Any] = {
            "corpus": corpus_name,
            "configs": {},
            "best_by_metric": {},
        }

        all_metrics: dict[str, dict[str, float]] = {}
        for cfg in config_names:
            run = self.evaluate(corpus_name, cfg, k=k)
            all_metrics[cfg] = run.metrics
            comparison["configs"][cfg] = run.to_dict()

        # Determinar mejor config por métrica
        for metric in [f"recall@{k}", f"precision@{k}", "mrr", f"ndcg@{k}", "map"]:
            best_cfg = max(all_metrics, key=lambda c: all_metrics[c].get(metric, 0))
            comparison["best_by_metric"][metric] = {
                "config": best_cfg,
                "value": all_metrics[best_cfg].get(metric, 0),
            }

        return comparison

    def get_results(self, n: int = 10) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._results[-n:]]

    def save_results(self, path: str | Path) -> None:
        data = {
            "results": self.get_results(100),
        }
        Path(path).write_text(json.dumps(data, indent=2) + "\n")

    def load_results(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text())
        for rd in data.get("results", []):
            run = EvaluationRun(
                corpus_name=rd["corpus"],
                config_name=rd["config"],
                metrics=rd["metrics"],
                per_query=rd["per_query"],
                timestamp=rd["timestamp"],
                latency_stats=rd.get("latency_stats", {}),
            )
            self._results.append(run)

    def reset(self) -> None:
        self._results.clear()
