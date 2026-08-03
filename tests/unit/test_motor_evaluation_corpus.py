"""Tests para motor/core/evaluation/ — corpus, metrics, evaluator."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from motor.core.evaluation.corpus import EvaluationCorpus, EvaluationQuery
from motor.core.evaluation.metrics import map_at_k, mrr, ndcg_at_k, precision_at_k, recall_at_k


class TestEvaluationQuery:
    def test_to_dict_from_dict_roundtrip(self) -> None:
        q = EvaluationQuery("q1", "texto", {"d1", "d2"}, {"d1": 1.0})
        d = q.to_dict()
        q2 = EvaluationQuery.from_dict(d)
        assert q2.query_id == "q1"
        assert q2.relevant_docs == {"d1", "d2"}
        assert q2.relevance_scores == {"d1": 1.0}

    def test_relevance_scores_default(self) -> None:
        q = EvaluationQuery("q1", "t", {"d1"})
        assert q.relevance_scores == {}

    def test_from_dict_sin_scores(self) -> None:
        q = EvaluationQuery.from_dict({"query_id": "q", "query_text": "t", "relevant_docs": ["a"]})
        assert q.relevance_scores == {}


class TestEvaluationCorpus:
    def test_add_get(self) -> None:
        c = EvaluationCorpus("test")
        q = EvaluationQuery("q1", "texto", {"d1"})
        c.add_query(q)
        assert c.get_query("q1") is q
        assert c.get_query("nope") is None
        assert len(c) == 1
        assert c.name == "test"

    def test_add_queries(self) -> None:
        c = EvaluationCorpus()
        c.add_queries([EvaluationQuery("a", "t1", set()), EvaluationQuery("b", "t2", set())])
        assert len(c) == 2

    def test_queries_copia(self) -> None:
        c = EvaluationCorpus()
        c.add_query(EvaluationQuery("a", "t", set()))
        qs = c.queries
        qs["b"] = EvaluationQuery("b", "x", set())  # no muta el corpus
        assert len(c) == 1

    def test_reemplaza_mismo_id(self) -> None:
        c = EvaluationCorpus()
        c.add_query(EvaluationQuery("a", "v1", set()))
        c.add_query(EvaluationQuery("a", "v2", set()))
        assert len(c) == 1
        assert c.get_query("a").query_text == "v2"

    def test_save_load(self, tmp_path) -> None:
        c = EvaluationCorpus("mi_corpus")
        c.add_query(EvaluationQuery("q1", "texto", {"d1", "d2"}, {"d1": 1.0}))
        p = tmp_path / "corpus.json"
        c.save(p)
        c2 = EvaluationCorpus.load(p)
        assert c2.name == "mi_corpus"
        assert len(c2) == 1
        assert c2.get_query("q1").relevant_docs == {"d1", "d2"}

    def test_to_dict(self) -> None:
        c = EvaluationCorpus("n")
        c.add_query(EvaluationQuery("q", "t", {"d"}))
        d = c.to_dict()
        assert d["name"] == "n"
        assert len(d["queries"]) == 1


class TestMetrics:
    def test_recall_at_k(self) -> None:
        relevant = {"d1", "d2", "d3"}
        retrieved = ["d1", "x", "d2"]
        assert recall_at_k(relevant, retrieved, 3) == pytest.approx(2 / 3)

    def test_recall_at_k_cero(self) -> None:
        assert recall_at_k(set(), ["a"], 1) == 0.0

    def test_precision_at_k(self) -> None:
        relevant = {"d1", "d2"}
        retrieved = ["d1", "x", "d2", "y"]
        assert precision_at_k(relevant, retrieved, 4) == pytest.approx(0.5)

    def test_mrr(self) -> None:
        relevant = {"d3"}
        assert mrr(relevant, ["d1", "d2", "d3"]) == pytest.approx(1 / 3)

    def test_mrr_sin_match(self) -> None:
        assert mrr({"x"}, ["a", "b"]) == 0.0

    def test_map_at_k(self) -> None:
        queries = [({"d1", "d2"}, ["d1", "x", "d2"]), ({"d3"}, ["d3", "x"])]
        ap = map_at_k(queries, 3)
        assert ap > 0.0

    def test_map_at_k_vacio(self) -> None:
        assert map_at_k([], 3) == 0.0

    def test_ndcg_at_k(self) -> None:
        relevant = {"d1", "d2"}
        retrieved = ["d1", "d2", "x"]
        n = ndcg_at_k(relevant, retrieved, 3)
        assert 0.0 < n <= 1.0

    def test_ndcg_sin_relevantes(self) -> None:
        assert ndcg_at_k(set(), ["a"], 1) == 0.0
