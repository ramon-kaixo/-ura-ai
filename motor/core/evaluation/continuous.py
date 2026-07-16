"""Evaluación continua integrada del RAG.

Integra EvaluationEngine, Experiment y RegressionDetector en un flujo
continuo: cargar corpus → ejecutar configuraciones → comparar vs baseline
→ generar reporte final. Modo CI con fail/warning por regresiones.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from motor.core.evaluation import (
    EvaluationCorpus,
    EvaluationEngine,
    Experiment,
)
from motor.core.evaluation.regression import (
    RegressionBaseline,
    RegressionDetector,
    RegressionReport,
)


class ContinuousEvaluationResult:
    """Resultado completo de una ejecución de evaluación continua."""

    def __init__(
        self,
        experiment_name: str,
        status: str,
        metrics_summary: dict[str, Any],
        regression_report: RegressionReport | None,
        experiment_results: list[dict[str, Any]],
        elapsed_seconds: float,
        errors: list[str],
    ) -> None:
        self.experiment_name = experiment_name
        self.status = status  # "pass", "fail", "warning"
        self.metrics_summary = metrics_summary
        self.regression_report = regression_report
        self.experiment_results = experiment_results
        self.elapsed_seconds = elapsed_seconds
        self.errors = errors

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment": self.experiment_name,
            "status": self.status,
            "passed": self.passed,
            "metrics_summary": self.metrics_summary,
            "regression_report": self.regression_report.to_dict()
                if self.regression_report else None,
            "experiment_results": self.experiment_results,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "errors": self.errors,
            "timestamp": time.time(),
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n")


class ContinuousEvaluator:
    """Evaluación continua integrada del RAG.

    Orquesta: cargar corpus → ejecutar experimento → comparar vs baseline
    → generar reporte CI.

    Uso:
        evaluator = ContinuousEvaluator()
        evaluator.add_config("bm25", bm25_fn)
        evaluator.add_config("semantic", semantic_fn)

        result = evaluator.run(corpus, baseline=my_baseline)
        if not result.passed:
            print("Regresiones detectadas!")
    """

    def __init__(self, name: str = "rag_eval") -> None:
        self._name = name
        self._configs: list[dict[str, Any]] = []
        self._fail_on_regression: bool = True
        self._critical_thresholds: dict[str, float] | None = None
        self._errors: list[str] = []

    def add_config(
        self,
        name: str,
        retrieve_fn: Callable,
        params: dict[str, Any] | None = None,
        description: str = "",
    ) -> None:
        self._configs.append({
            "name": name,
            "fn": retrieve_fn,
            "params": params or {},
            "description": description,
        })

    def set_fail_on_regression(self, value: bool) -> None:  # noqa: FBT001
        self._fail_on_regression = value

    def set_critical_thresholds(self, thresholds: dict[str, float]) -> None:
        self._critical_thresholds = thresholds

    def run(  # noqa: C901
        self,
        corpus: EvaluationCorpus,
        k: int = 10,
        baseline: RegressionBaseline | None = None,
        baseline_path: str | None = None,
    ) -> ContinuousEvaluationResult:
        """Ejecuta evaluación completa.

        Args:
            corpus: Corpus de evaluación.
            k: Top K para métricas.
            baseline: Baseline preexistente (opcional).
            baseline_path: Ruta para cargar/guardar baseline.

        Returns:
            ContinuousEvaluationResult con status, reportes y métricas.
        """
        t_start = time.time()
        self._errors = []

        if len(corpus) == 0:
            self._errors.append("Corpus vacío — no se ejecutó evaluación")

        # Registrar retrievers en engine
        engine = EvaluationEngine()
        engine.register_corpus("default", corpus)
        for cfg in self._configs:
            engine.register_retriever(cfg["name"], cfg["fn"])

        # Ejecutar experimento
        exp = Experiment(self._name, corpus)
        for cfg in self._configs:
            exp.add_config(
                name=cfg["name"],
                retrieve_fn=cfg["fn"],
                params=cfg["params"],
                description=cfg["description"],
            )

        experiment_results = exp.run(k=k)
        comparison = exp.compare()

        # Cargar baseline
        loaded_baseline = None
        if baseline:
            loaded_baseline = baseline
        elif baseline_path and Path(baseline_path).exists():
            loaded_baseline = RegressionBaseline.load(baseline_path)
            # Actualizar con resultados actuales
            loaded_baseline.set_results(experiment_results)

        # Detectar regresiones
        regression_report = None
        if loaded_baseline:
            thresholds = self._critical_thresholds
            detector = RegressionDetector(loaded_baseline, thresholds=thresholds)
            regression_report = detector.check(experiment_results)

            # Guardar baseline actualizada
            if baseline_path:
                loaded_baseline.save(baseline_path)
        else:
            # Crear nueva baseline desde resultados
            new_baseline = RegressionBaseline(self._name)
            new_baseline.set_results(experiment_results)
            if baseline_path:
                new_baseline.save(baseline_path)

        # Determinar status
        status = "pass"
        if regression_report and not regression_report.passed:
            status = "fail" if self._fail_on_regression else "warning"

        if self._errors and status == "pass":
            status = "warning"

        elapsed = time.time() - t_start

        # Resumen de métricas
        metrics_summary = comparison if "error" not in comparison else {"error": "no data"}

        # Resultados serializables
        serialized_results = [r.to_dict() for r in experiment_results]

        return ContinuousEvaluationResult(
            experiment_name=self._name,
            status=status,
            metrics_summary=metrics_summary,
            regression_report=regression_report,
            experiment_results=serialized_results,
            elapsed_seconds=elapsed,
            errors=self._errors,
        )
