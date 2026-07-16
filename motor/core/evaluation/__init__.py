"""Evaluación de Retrieval (F21).

Framework para evaluar configuraciones de retrieval contra corpus
de evaluación con métricas estándar (Recall@K, Precision@K, MRR, MAP, nDCG@K).
"""

from motor.core.evaluation.corpus import EvaluationCorpus, EvaluationQuery
from motor.core.evaluation.evaluator import EvaluationEngine, EvaluationRun, RetrievalResult
from motor.core.evaluation.experiment import Experiment, ExperimentConfig, ExperimentResult
from motor.core.evaluation.regression import (
    RegressionBaseline,
    RegressionDetector,
    RegressionFinding,
    RegressionReport,
)
from motor.core.evaluation.metrics import (
    map_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

__all__ = [
    "EvaluationCorpus",
    "EvaluationEngine",
    "EvaluationQuery",
    "EvaluationRun",
    "Experiment",
    "ExperimentConfig",
    "ExperimentResult",
    "RegressionBaseline",
    "RegressionDetector",
    "RegressionFinding",
    "RegressionReport",
    "RetrievalResult",
    "map_at_k",
    "mrr",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
]
