"""Tests del benchmark RAG (F21-B2).





Verifica:
1. Benchmark con un solo retriever
2. Benchmark con múltiples retrievers
3. Exportación JSON correcta
4. Ranking automático
5. Corpus vacío manejado
6. Resultados repetibles (deterministas)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow  # G4: requieren scripts/servicios de benchmark pesados

import json
from pathlib import Path

from motor.core.evaluation import EvaluationCorpus, EvaluationEngine, EvaluationQuery
from motor.core.evaluation.corpus import EvaluationCorpus as EC





def _crear_corpus_test() -> EvaluationCorpus:
    corpus = EC("test")
    queries = [
        EvaluationQuery("q1", "texto uno", {"d1", "d3"}),
        EvaluationQuery("q2", "texto dos", {"d2"}),
    ]
    corpus.add_queries(queries)
    return corpus


def _retriever_a(query: str) -> list[str]:
    if "uno" in query:
        return ["d1", "d2", "d3"]
    return ["d2", "d1", "d3"]


def _retriever_b(query: str) -> list[str]:
    if "uno" in query:
        return ["d3", "d2", "d1"]
    return ["d2", "d3", "d1"]


def _retriever_worse(query: str) -> list[str]:
    return ["d4", "d5", "d6"]


class TestBenchmarkRAG:
    def test_single_retriever(self) -> None:
        corpus = _crear_corpus_test()
        engine = EvaluationEngine()
        engine.register_corpus("c", corpus)
        engine.register_retriever("bm25", _retriever_a)
        run = engine.evaluate("c", "bm25", k=3)
        assert run.metrics["recall@3"] >= 0.5
        assert run.metrics["mrr"] >= 0.5

    def test_multiple_retrievers(self) -> None:
        corpus = _crear_corpus_test()
        engine = EvaluationEngine()
        engine.register_corpus("c", corpus)
        engine.register_retriever("a", _retriever_a)
        engine.register_retriever("b", _retriever_b)
        engine.register_retriever("worse", _retriever_worse)

        comparison = engine.compare("c", ["a", "b", "worse"], k=3)
        assert "configs" in comparison
        assert len(comparison["configs"]) == 3
        assert "a" in comparison["configs"]
        assert "b" in comparison["configs"]
        assert "worse" in comparison["configs"]

    def test_json_output(self, tmp_path: Path) -> None:
        corpus = _crear_corpus_test()
        engine = EvaluationEngine()
        engine.register_corpus("c", corpus)
        engine.register_retriever("r", _retriever_a)
        engine.evaluate("c", "r", k=3)

        path = tmp_path / "result.json"
        engine.save_results(str(path))
        assert path.exists()
        data = json.loads(path.read_text())
        assert "results" in data
        assert len(data["results"]) == 1
        # Verificar schema
        r = data["results"][0]
        assert "corpus" in r
        assert "config" in r
        assert "metrics" in r
        assert "per_query" in r
        assert "timestamp" in r
        assert "latency_stats" in r

    def test_ranking(self) -> None:
        """Verifica que el mejor retriever obtiene el ranking más alto."""
        corpus = _crear_corpus_test()
        engine = EvaluationEngine()
        engine.register_corpus("c", corpus)
        engine.register_retriever("a", _retriever_a)
        engine.register_retriever("worse", _retriever_worse)

        comparison = engine.compare("c", ["a", "worse"], k=3)
        # 'a' debe ser mejor que 'worse' en recall@3
        best_recall = comparison["best_by_metric"]["recall@3"]
        assert best_recall["config"] == "a"
        assert best_recall["value"] > 0

    def test_empty_corpus(self) -> None:
        corpus = EC("empty")
        engine = EvaluationEngine()
        engine.register_corpus("c", corpus)
        engine.register_retriever("r", _retriever_a)
        run = engine.evaluate("c", "r", k=3)
        # Sin consultas, las métricas deben ser 0
        for metric, value in run.metrics.items():
            assert value == 0.0, f"{metric}={value} should be 0"

    def test_repeatable_results(self) -> None:
        """Dos ejecuciones con el mismo corpus y retriever deben dar el mismo resultado."""
        corpus = _crear_corpus_test()

        engine1 = EvaluationEngine()
        engine1.register_corpus("c", corpus)
        engine1.register_retriever("r", _retriever_a)
        run1 = engine1.evaluate("c", "r", k=3)

        engine2 = EvaluationEngine()
        engine2.register_corpus("c", corpus)
        engine2.register_retriever("r", _retriever_a)
        run2 = engine2.evaluate("c", "r", k=3)

        for metric in run1.metrics:
            assert run1.metrics[metric] == run2.metrics[metric], (
                f"{metric}: {run1.metrics[metric]} != {run2.metrics[metric]}"
            )
