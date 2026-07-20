"""Reranking module — reordena top-K candidatos usando cross-encoder."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

log = logging.getLogger("ura.reranking")

GOLDEN_DIR = Path(__file__).resolve().parent.parent.parent.parent / "knowledge" / "evaluation" / "golden_docs"


class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class NoOpReranker(BaseReranker):
    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return candidates


class CrossEncoderReranker(BaseReranker):
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-2-v2") -> None:
        self._model_name = model_name
        self._tokenizer = None
        self._model = None
        self._docs: dict[str, str] = {}
        self._load_docs()
        self._load_model()

    def _load_docs(self) -> None:
        if GOLDEN_DIR.exists():
            for md_file in GOLDEN_DIR.glob("*.md"):
                self._docs[md_file.stem] = md_file.read_text(encoding="utf-8")

    def _load_model(self) -> None:
        import os

        cache_dir = Path.home() / ".cache" / "hf_cache"
        os.environ.setdefault("HF_HOME", str(cache_dir))
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)  # nosec B615
            self._model = AutoModelForSequenceClassification.from_pretrained(self._model_name)  # nosec B615
            self._model.eval()
            log.info("CrossEncoder cargado: %s", self._model_name)
        except Exception as e:
            log.warning("Error cargando cross-encoder %s: %s — usando NoOp fallback", self._model_name, e)

    @property
    def available(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.available or not candidates:
            return candidates

        pairs: list[tuple[str, str]] = []
        doc_texts: list[str] = []

        for c in candidates:
            doc_id = c.get("doc_id", "")
            text = self._docs.get(doc_id, doc_id)
            pairs.append((query, text))
            doc_texts.append(text)

        start = time.monotonic()
        import torch

        inputs = self._tokenizer(
            pairs,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=512,
        )
        with torch.no_grad():
            outputs = self._model(**inputs)
        scores = outputs.logits.squeeze(-1).tolist()
        if not isinstance(scores, list):
            scores = [scores]

        elapsed = (time.monotonic() - start) * 1000

        scored = list(zip(candidates, scores, strict=False))
        scored.sort(key=lambda x: x[1], reverse=True)

        reranked: list[dict[str, Any]] = []
        for rank, (orig, score) in enumerate(scored):
            entry = dict(orig)
            entry["rerank_score"] = round(score, 4)
            entry["rerank_latency_ms"] = round(elapsed, 2)
            entry["rank"] = rank
            entry["source"] = orig.get("source", "reranked")
            if "hybrid_score" in entry:
                entry["pre_rerank_score"] = entry["hybrid_score"]
            elif "score" in entry:
                entry["pre_rerank_score"] = entry["score"]
            entry["score"] = score  # override score with reranker score
            reranked.append(entry)

        return reranked
