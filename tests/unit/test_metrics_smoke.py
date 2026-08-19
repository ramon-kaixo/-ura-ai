"""Tests smoke + casos de ranking para evaluation/metrics (100x100)."""

import pytest

from motor.core.evaluation.metrics import (
    recall_at_k,
    precision_at_k,
    mrr,
    map_at_k,
    _average_precision,
    _dcg,
    ndcg_at_k,
)


def test_import_metrics():
    """El módulo importa sin errores."""
    assert recall_at_k is not None


def test_recall_at_k_basico():
    """Recall@K: casos básicos y límites."""
    relevant = {"a", "b", "c"}
    assert recall_at_k(relevant, ["a", "b", "x"], 2) == pytest.approx(2 / 3)
    assert recall_at_k(relevant, ["x", "y"], 2) == 0.0
    assert recall_at_k(set(), ["a"], 1) == 0.0
    assert recall_at_k(relevant, ["a", "a", "a"], 3) == pytest.approx(1.0)  # duplicados acotados


def test_precision_at_k_basico():
    """Precision@K: casos básicos."""
    relevant = {"a", "b"}
    assert precision_at_k(relevant, ["a", "x"], 2) == pytest.approx(0.5)
    assert precision_at_k(relevant, ["a", "b"], 2) == 1.0
    assert precision_at_k(relevant, [], 5) == 0.0


def test_mrr_basico():
    """MRR: primer relevante y ninguno."""
    assert mrr({"b"}, ["x", "b", "c"]) == pytest.approx(0.5)
    assert mrr({"b"}, ["x", "y"]) == 0.0
    assert mrr({"b"}, ["b"]) == 1.0


def test_map_at_k_basico():
    """MAP@K: múltiples consultas."""
    queries = [( {"a"}, ["a", "x"]), ({"b"}, ["b"])]
    assert map_at_k(queries, 5) == pytest.approx(1.0)
    assert map_at_k([], 5) == 0.0


def test_average_precision():
    """AP: proporción de relevantes en retrieved."""
    assert _average_precision({"a"}, ["a", "b"]) == pytest.approx(1.0)
    assert _average_precision({"a"}, ["b", "c"]) == 0.0


def test_dcg_y_ndcg():
    """nDCG: con y sin relevance_scores."""
    relevant = {"a", "b"}
    r = ndcg_at_k(relevant, ["a", "b", "x"], 3)
    assert 0.0 <= r <= 1.0
    r2 = ndcg_at_k(relevant, ["a", "b"], 2, {"a": 1.0, "b": 0.5})
    assert 0.0 <= r2 <= 1.0
    assert _dcg([1.0, 0.5], 2) > 0.0
    assert _dcg([], 5) == 0.0
    assert ndcg_at_k(relevant, [], 3) == 0.0


def test_ramas_restantes():
    """Ramas: relevant vacío en AP; idcg<=0 en nDCG."""
    assert _average_precision(set(), ["a"]) == 0.0
    assert ndcg_at_k({"a"}, ["x", "y"], 2) == 0.0  # sin docs relevantes -> idcg 0


def test_ndcg_idcg_cero():
    """Rama: relevance_scores con todos los relevantes en 0 -> idcg 0."""
    assert ndcg_at_k({"a"}, ["x"], 1, {"a": 0.0}) == 0.0
