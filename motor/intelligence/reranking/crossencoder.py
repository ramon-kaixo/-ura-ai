"""CrossEncoderReranker — reranking con cross-encoder especializado (sentence-transformers)."""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from motor.intelligence.reranking.base import BaseReranker

log = logging.getLogger("ura.reranker.crossencoder")

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker(BaseReranker):
    def __init__(
        self,
        model_name: str = MODEL_NAME,
        top_k: int = 10,
        cache_folder: str = "/tmp/hf_hub",
    ) -> None:
        self._model_name = model_name
        self._top_k = top_k
        self._model = None
        self._cache_folder = cache_folder
        self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name, cache_folder=self._cache_folder)
            log.info("CrossEncoder cargado: %s", self._model_name)
        except Exception as e:
            log.error("Error cargando CrossEncoder: %s", e)

    @property
    def available(self) -> bool:
        return self._model is not None

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not candidates or self._model is None:
            return candidates

        to_rerank = candidates[:self._top_k]
        pairs = [(query, self._get_text(doc)) for doc in to_rerank]

        start = time.monotonic()
        try:
            logits = self._model.predict(pairs)
        except Exception as e:
            log.warning("CrossEncoder predict falló: %s", e)
            return candidates
        elapsed = (time.monotonic() - start) * 1000

        scores = [self._sigmoid(float(s)) for s in logits]
        for doc, score in zip(to_rerank, scores):
            doc["reranker_score"] = score
            doc["reranker_latency_ms"] = round(elapsed / len(scores), 2)
            doc["reranker_model"] = self._model_name

        to_rerank.sort(key=lambda x: x["reranker_score"], reverse=True)
        for rank, doc in enumerate(to_rerank):
            doc["rank"] = rank

        return to_rerank + candidates[self._top_k:]

    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    def _get_text(self, doc: dict[str, Any]) -> str:
        doc_id = doc.get("doc_id", "")
        text = doc.get("payload", {}).get("texto", "")
        if not text:
            try:
                from pathlib import Path
                p = Path(__file__).resolve().parent.parent.parent.parent / "knowledge" / "evaluation" / "golden_docs" / f"{doc_id}.md"
                if p.exists():
                    text = p.read_text(encoding="utf-8")
            except Exception:
                pass
        return text[:2000] or doc_id
