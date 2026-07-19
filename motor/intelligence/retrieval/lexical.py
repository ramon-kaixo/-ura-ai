"""LexicalRetriever — búsqueda BM25 sobre corpus en memoria."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

log = logging.getLogger("ura.retrieval.lexical")

GOLDEN_DIR = Path(__file__).resolve().parent.parent.parent.parent / "knowledge" / "evaluation" / "golden_docs"


class LexicalRetriever:
    def __init__(self, docs_dir: str | Path = GOLDEN_DIR) -> None:
        self._docs: list[dict[str, Any]] = []
        self._corpus: list[str] = []
        self._bm25: BM25Okapi | None = None
        self._load_docs(docs_dir)

    def _load_docs(self, docs_dir: str | Path) -> None:
        path = Path(docs_dir)
        if not path.exists():
            log.warning("Golden docs dir not found: %s", path)
            return
        for md_file in sorted(path.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            doc_id = md_file.stem
            self._docs.append({"doc_id": doc_id, "text": text, "source": doc_id})
            self._corpus.append(text)
        if self._corpus:
            self._bm25 = BM25Okapi([doc.split() for doc in self._corpus])
            log.info("BM25 index: %d docs from %s", len(self._docs), path)

    def search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        if self._bm25 is None:
            return []

        start = time.monotonic()
        query_tokens = query.split()
        scores = self._bm25.get_scores(query_tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        results = []
        for rank, idx in enumerate(top_indices):
            if scores[idx] <= 0:
                continue
            results.append(
                {
                    "doc_id": self._docs[idx]["doc_id"],
                    "score": float(scores[idx]),
                    "rank": rank,
                    "latency_ms": round((time.monotonic() - start) * 1000, 2),
                    "source": "lexical",
                },
            )
        return results
