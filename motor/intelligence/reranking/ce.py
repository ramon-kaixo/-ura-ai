from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from motor.intelligence.reranking.base import BaseReranker

log = logging.getLogger("ura.reranker.ce")

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
GOLDEN_DIR = Path(__file__).resolve().parent.parent.parent.parent / "knowledge" / "evaluation" / "golden_docs"


class CrossEncoderReranker(BaseReranker):
    def __init__(
        self,
        model_name: str = MODEL_NAME,
        device: str | None = None,
        top_k: int = 10,
        batch_size: int = 10,
    ) -> None:
        self._model_name = model_name
        self._top_k = top_k
        self._batch_size = batch_size
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._tokenizer: Any = None
        self._model: Any = None
        self._loaded = False
        self._doc_cache: dict[str, str] = {}
        self._load_docs()

    def _load_docs(self) -> None:
        if GOLDEN_DIR.exists():
            for f in sorted(GOLDEN_DIR.glob("*.md")):
                self._doc_cache[f.stem] = f.read_text(encoding="utf-8")

    def _lazy_load(self) -> None:
        if self._loaded:
            return
        log.info("Cargando cross-encoder %s en %s...", self._model_name, self._device)
        start = time.monotonic()
        self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)  # nosec B615 - modelo local controlado, no hay revision specifica
        self._model = AutoModelForSequenceClassification.from_pretrained(self._model_name)  # nosec B615
        self._model.to(self._device)
        self._model.eval()
        elapsed = (time.monotonic() - start) * 1000
        log.info("Cross-encoder cargado en %.0fms", elapsed)
        self._loaded = True

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return candidates

        self._lazy_load()
        to_rerank = candidates[: self._top_k]
        texts = self._get_texts(to_rerank)
        pairs = [(query, text) for text in texts]

        start = time.monotonic()
        scores = self._score_batch(pairs)
        elapsed = (time.monotonic() - start) * 1000

        for i, doc in enumerate(to_rerank):
            doc["reranker_score"] = float(scores[i])
            doc["reranker_latency_ms"] = round(elapsed, 2)
            doc["reranker_model"] = self._model_name

        to_rerank.sort(key=lambda x: x["reranker_score"], reverse=True)
        for rank, doc in enumerate(to_rerank):
            doc["rank"] = rank
            doc["score"] = doc["reranker_score"]

        return to_rerank

    def _get_texts(self, candidates: list[dict]) -> list[str]:
        return [self._doc_cache.get(doc.get("doc_id", ""), "")[:2000] for doc in candidates]

    def _score_batch(self, pairs: list[tuple[str, str]]) -> list[float]:
        all_scores: list[float] = []
        for i in range(0, len(pairs), self._batch_size):
            batch = pairs[i : i + self._batch_size]
            features = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512,
            ).to(self._device)
            with torch.no_grad():
                logits = self._model(**features).logits
                batch_scores = logits.squeeze(-1).cpu().numpy().tolist()
            if isinstance(batch_scores, float):
                batch_scores = [batch_scores]
            all_scores.extend(batch_scores)
        return all_scores
