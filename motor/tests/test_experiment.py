"""Tests del framework de experimentación RAG (F21-B3).

Verifica:
1. Experimento simple (1 configuración)
2. Múltiples configuraciones
3. Comparación automática con rankings
4. Exportación JSON
5. Reporte textual
6. Resultados repetibles
7. Experimento vacío (sin configs)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from motor.core.evaluation.corpus import EvaluationCorpus, EvaluationQuery
from motor.core.evaluation.experiment import Experiment

if TYPE_CHECKING:
    from pathlib import Path


def _crear_corpus() -> EvaluationCorpus:
    corpus = EvaluationCorpus("test")
    corpus.add_queries(
        [
            EvaluationQuery("q1", "texto uno", {"d1", "d3"}),
            EvaluationQuery("q2", "texto dos", {"d2"}),
        ],
    )
    return corpus


def _retriever_base(query: str) -> list[str]:
    # Base: resultados parcialmente relevantes
    if "uno" in query:
        return ["d1", "d4", "d5", "d6", "d2", "d3"]
    return ["d2", "d4", "d5", "d6", "d1", "d3"]


def _retriever_mejor(query: str) -> list[str]:
    # Mejor: resultados relevantes primero, máximo recall
    if "uno" in query:
        return ["d1", "d3", "d2", "d4", "d5", "d6"]
    return ["d2", "d1", "d3", "d4", "d5", "d6"]


def _retriever_peor(query: str) -> list[str]:
    return ["d4", "d5", "d6"]


class TestExperiment:
    def test_single_experiment(self) -> None:
        exp = Experiment("test", _crear_corpus())
        exp.add_config("base", _retriever_base)
        results = exp.run(k=3)
        assert len(results) == 1
        assert results[0].config_name == "base"
        assert results[0].metrics["recall@3"] >= 0.5

    def test_multiple_experiments(self) -> None:
        exp = Experiment("multi", _crear_corpus())
        exp.add_config("base", _retriever_base)
        exp.add_config("mejor", _retriever_mejor)
        exp.add_config("peor", _retriever_peor)
        results = exp.run(k=3)
        assert len(results) == 3
        names = [r.config_name for r in results]
        assert "base" in names
        assert "mejor" in names
        assert "peor" in names

    def test_experiment_compare(self) -> None:
        exp = Experiment("compare", _crear_corpus())
        exp.add_config("base", _retriever_base)
        exp.add_config("mejor", _retriever_mejor)
        exp.add_config("peor", _retriever_peor)
        exp.run(k=3)
        comp = exp.compare()
        assert "rankings" in comp
        assert "general_ranking" in comp
        assert len(comp["general_ranking"]) == 3
        assert comp["winner"] is not None

    def test_experiment_ranking(self) -> None:
        """El mejor retriever debe tener el ranking más alto."""
        exp = Experiment("ranking", _crear_corpus())
        exp.add_config("base", _retriever_base)
        exp.add_config("mejor", _retriever_mejor)
        exp.add_config("peor", _retriever_peor)
        exp.run(k=3)
        comp = exp.compare()
        # 'mejor' debe tener mejor recall que 'peor'
        recall_ranking = comp["rankings"].get("recall@3", [])
        mejor_rank = next(r for r in recall_ranking if r["config"] == "mejor")
        peor_rank = next(r for r in recall_ranking if r["config"] == "peor")
        assert mejor_rank["value"] > peor_rank["value"]
        # 'mejor' debe ser el ganador general
        assert comp["winner"] == "mejor"

    def test_json_export(self, tmp_path: Path) -> None:
        exp = Experiment("json_test", _crear_corpus())
        exp.add_config("base", _retriever_base)
        exp.run(k=3)
        path = tmp_path / "experimento.json"
        exp.save(str(path))
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["experiment"] == "json_test"
        assert "results" in data
        assert "comparison" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["config"] == "base"

    def test_json_load(self, tmp_path: Path) -> None:
        """Cargar JSON guardado (como dict)."""
        exp = Experiment("load_test", _crear_corpus())
        exp.add_config("base", _retriever_base)
        exp.run(k=3)
        path = tmp_path / "exp.json"
        exp.save(str(path))

        loaded = Experiment.load(str(path))
        assert loaded["experiment"] == "load_test"
        assert len(loaded["results"]) == 1

    def test_report(self) -> None:
        exp = Experiment("report_test", _crear_corpus())
        exp.add_config("base", _retriever_base)
        exp.add_config("mejor", _retriever_mejor)
        exp.run(k=3)
        report = exp.report()
        assert "report_test" in report
        assert "Ranking General" in report
        assert "Ganador" in report

    def test_repeatable_results(self) -> None:
        """Dos ejecuciones del mismo experimento deben dar los mismos resultados."""
        exp1 = Experiment("r1", _crear_corpus())
        exp1.add_config("base", _retriever_base)
        exp1.run(k=3)

        exp2 = Experiment("r2", _crear_corpus())
        exp2.add_config("base", _retriever_base)
        exp2.run(k=3)

        for m in exp1.results[0].metrics:
            assert exp1.results[0].metrics[m] == exp2.results[0].metrics[m], (
                f"Mismatch for {m}: {exp1.results[0].metrics[m]} != {exp2.results[0].metrics[m]}"
            )

    def test_empty_experiment(self) -> None:
        """Experimento sin configuraciones."""
        exp = Experiment("empty", _crear_corpus())
        results = exp.run(k=3)
        assert len(results) == 0
        comp = exp.compare()
        assert "error" in comp

    def test_experiment_importable(self) -> None:
        from motor.core.evaluation import Experiment

        assert Experiment is not None
