"""Evaluación de Retrieval (F21).

Framework para evaluar configuraciones de retrieval contra corpus
de evaluación con métricas estándar (Recall@K, Precision@K, MRR, MAP, nDCG@K).
"""

from motor.core.evaluation.corpus import EvaluationCorpus, EvaluationQuery
from motor.core.evaluation.evaluator import EvaluationEngine, EvaluationRun, RetrievalResult
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
    "RetrievalResult",
    "map_at_k",
    "mrr",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
]
