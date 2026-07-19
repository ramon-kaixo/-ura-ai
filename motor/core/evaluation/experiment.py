"""Framework de experimentación reproducible para configuraciones RAG.

Permite registrar múltiples configuraciones (retriever + parámetros),
ejecutarlas sobre el mismo corpus, comparar métricas y generar ranking.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from motor.core.evaluation.corpus import EvaluationCorpus

from motor.core.evaluation.evaluator import EvaluationEngine


@dataclass
class ExperimentConfig:
    """Configuración de un experimento: retriever + nombre + parámetros."""

    name: str
    retrieve_fn: Callable
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class ExperimentResult:
    """Resultado de un experimento."""

    config_name: str
    metrics: dict[str, float]
    per_query: list[dict[str, Any]]
    latency_stats: dict[str, float]
    params: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config_name,
            "params": self.params,
            "metrics": self.metrics,
            "latency_stats": self.latency_stats,
        }


@dataclass
class ExperimentRanking:
    """Ranking de configuraciones para una métrica."""

    metric: str
    k: int
    entries: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "k": self.k,
            "entries": self.entries,
        }


class Experiment:
    """Experimento reproducible de evaluación RAG.

    Uso:
        exp = Experiment("Mi Experimento", corpus)
        exp.add_config("bm25", bm25_fn, {"k1": 1.2, "b": 0.75})
        exp.add_config("semantic", semantic_fn, {"model": "all-MiniLM"})
        exp.run(k=10)
        exp.save("resultados.json")
        print(exp.report())
    """

    def __init__(
        self,
        name: str,
        corpus: EvaluationCorpus,
        description: str = "",
    ) -> None:
        self._name = name
        self._description = description
        self._corpus = corpus
        self._configs: list[ExperimentConfig] = []
        self._results: list[ExperimentResult] = []
        self._engine = EvaluationEngine()
        self._k: int = 10
        self._start_time: float = 0.0
        self._end_time: float = 0.0

    @property
    def name(self) -> str:
        return self._name

    @property
    def configs(self) -> list[ExperimentConfig]:
        return list(self._configs)

    @property
    def results(self) -> list[ExperimentResult]:
        return list(self._results)

    def add_config(
        self,
        name: str,
        retrieve_fn: Callable,
        params: dict[str, Any] | None = None,
        description: str = "",
    ) -> None:
        """Registra una configuración para el experimento."""
        self._configs.append(
            ExperimentConfig(
                name=name,
                retrieve_fn=retrieve_fn,
                params=params or {},
                description=description,
            ),
        )

    def run(self, k: int = 10) -> list[ExperimentResult]:
        """Ejecuta todas las configuraciones registradas.

        Returns:
            Lista de ExperimentResult, uno por configuración.

        """
        self._k = k
        self._results.clear()
        self._engine = EvaluationEngine()
        self._engine.register_corpus("default", self._corpus)

        for cfg in self._configs:
            self._engine.register_retriever(cfg.name, cfg.retrieve_fn)

        self._start_time = time.time()

        for cfg in self._configs:
            run = self._engine.evaluate("default", cfg.name, k=k)
            result = ExperimentResult(
                config_name=cfg.name,
                metrics=run.metrics,
                per_query=run.per_query,
                latency_stats=run.latency_stats,
                params=cfg.params,
            )
            self._results.append(result)

        self._end_time = time.time()
        return self._results

    def compare(self) -> dict[str, Any]:
        """Compara todas las configuraciones ejecutadas.

        Returns:
            Dict con rankings por métrica y ganador general.

        """
        if not self._results:
            return {"error": "no results", "configs": []}

        rankings: dict[str, list[dict[str, Any]]] = {}
        metrics = [
            f"recall@{self._k}",
            f"precision@{self._k}",
            "mrr",
            f"ndcg@{self._k}",
            "map",
        ]

        for metric in metrics:
            ranked = sorted(
                [(r.config_name, r.metrics.get(metric, 0)) for r in self._results],
                key=lambda x: x[1],
                reverse=True,
            )
            rankings[metric] = [{"config": name, "value": round(value, 4)} for name, value in ranked]

        # Ganador general (promedio de rankings normalizados)
        config_scores: dict[str, float] = {}
        for r in self._results:
            scores = [r.metrics.get(m, 0) for m in metrics]
            config_scores[r.config_name] = statistics.mean(scores)

        general = sorted(
            [(name, round(score, 4)) for name, score in config_scores.items()],
            key=lambda x: x[1],
            reverse=True,
        )

        elapsed = self._end_time - self._start_time if self._end_time > 0 else 0

        return {
            "experiment": self._name,
            "k": self._k,
            "total_configs": len(self._configs),
            "total_queries": len(self._corpus),
            "elapsed_seconds": round(elapsed, 2),
            "rankings": rankings,
            "general_ranking": [
                {"rank": i + 1, "config": name, "score": score} for i, (name, score) in enumerate(general)
            ],
            "winner": general[0][0] if general else None,
            "winner_score": general[0][1] if general else None,
        }

    def report(self) -> str:
        """Genera reporte textual del experimento."""
        comp = self.compare()
        if "error" in comp:
            return f"Error: {comp['error']}"

        lines = [
            f"Experimento: {self._name}",
            f"  Consultas: {comp['total_queries']}",
            f"  Configuraciones: {comp['total_configs']}",
            f"  K: {comp['k']}",
            f"  Duración: {comp['elapsed_seconds']}s",
            "",
            "  Ranking General:",
        ]

        lines.extend(
            f"    #{entry['rank']}  {entry['config']:<15} {entry['score']:.4f}" for entry in comp["general_ranking"]
        )

        if comp.get("winner"):
            lines.append(f"\n  Ganador: {comp['winner']} (score: {comp['winner_score']:.4f})")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Exporta el experimento completo a dict."""
        comp = self.compare()
        return {
            "experiment": self._name,
            "description": self._description,
            "k": self._k,
            "results": [r.to_dict() for r in self._results],
            "comparison": comp,
        }

    def save(self, path: str | Path) -> None:
        """Persiste el experimento a JSON."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> ExperimentResult:
        """Carga resultados de experimento desde JSON.

        Nota: solo carga los resultados, no las configuraciones originales.
        Para re-ejecutar, crear un nuevo Experiment con las mismas configs.
        """
        return json.loads(Path(path).read_text())
        # Devolvemos un resultado directo (o podríamos reconstruir parcialmente)
