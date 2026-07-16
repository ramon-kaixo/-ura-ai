"""Corpus de evaluación: consultas con juicios de relevancia."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class EvaluationQuery:
    """Una consulta de evaluación con sus documentos relevantes."""

    __slots__ = ("query_id", "query_text", "relevance_scores", "relevant_docs")

    def __init__(
        self,
        query_id: str,
        query_text: str,
        relevant_docs: set[str],
        relevance_scores: dict[str, float] | None = None,
    ) -> None:
        self.query_id = query_id
        self.query_text = query_text
        self.relevant_docs = relevant_docs
        self.relevance_scores = relevance_scores or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "relevant_docs": list(self.relevant_docs),
            "relevance_scores": self.relevance_scores,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationQuery:
        return cls(
            query_id=data["query_id"],
            query_text=data["query_text"],
            relevant_docs=set(data.get("relevant_docs", [])),
            relevance_scores=data.get("relevance_scores"),
        )


class EvaluationCorpus:
    """Colección de consultas de evaluación.

    Thread-safe. Persistible a JSON.
    """

    def __init__(self, name: str = "default") -> None:
        self._name = name
        self._queries: dict[str, EvaluationQuery] = {}
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def queries(self) -> dict[str, EvaluationQuery]:
        with self._lock:
            return dict(self._queries)

    def add_query(self, query: EvaluationQuery) -> None:
        with self._lock:
            self._queries[query.query_id] = query

    def add_queries(self, queries: list[EvaluationQuery]) -> None:
        with self._lock:
            for q in queries:
                self._queries[q.query_id] = q

    def get_query(self, query_id: str) -> EvaluationQuery | None:
        with self._lock:
            return self._queries.get(query_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._queries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self._name,
            "queries": [q.to_dict() for q in self.queries.values()],
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> EvaluationCorpus:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        corpus = cls(name=data.get("name", "loaded"))
        for qd in data.get("queries", []):
            corpus.add_query(EvaluationQuery.from_dict(qd))
        return corpus
