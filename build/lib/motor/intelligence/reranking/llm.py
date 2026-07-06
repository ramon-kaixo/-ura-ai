"""LLMReranker — reordena usando un LLM (Ollama) para puntuar relevancia."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

from motor.intelligence.reranking.base import BaseReranker

log = logging.getLogger("ura.reranker.llm")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:7b"
GOLDEN_DIR = Path(__file__).resolve().parent.parent.parent.parent / "knowledge" / "evaluation" / "golden_docs"


class LLMReranker(BaseReranker):
    def __init__(
        self,
        model: str = MODEL,
        ollama_url: str = OLLAMA_URL,
        timeout: int = 30,
        top_k: int = 10,
    ) -> None:
        self._model = model
        self._url = ollama_url
        self._timeout = timeout
        self._top_k = top_k
        self._doc_cache: dict[str, str] = {}
        self._load_docs()

    def _load_docs(self) -> None:
        if GOLDEN_DIR.exists():
            for f in sorted(GOLDEN_DIR.glob("*.md")):
                self._doc_cache[f.stem] = f.read_text(encoding="utf-8")

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return candidates

        to_rerank = candidates[:self._top_k]
        scored: list[dict[str, Any]] = []

        for doc in to_rerank:
            start = time.monotonic()
            doc_id = doc.get("doc_id", "")
            text = self._doc_cache.get(doc_id, "") or doc.get("payload", {}).get("texto", "")
            score = self._score(query, doc_id, text) if text else 0.0
            elapsed = (time.monotonic() - start) * 1000
            doc["reranker_score"] = score
            doc["reranker_latency_ms"] = round(elapsed, 2)
            doc["reranker_model"] = self._model
            scored.append(doc)

        scored.sort(key=lambda x: x["reranker_score"], reverse=True)
        for rank, doc in enumerate(scored):
            doc["rank"] = rank
            doc["score"] = doc["reranker_score"]

        return scored

    def _score(self, query: str, doc_id: str, text: str) -> float:
        prompt = (
            f"Query: {query}\n\n"
            f"Document: {text[:2000]}\n\n"
            "Rate relevance 0-10. Only respond with a single number."
        )

        try:
            resp = httpx.post(
                self._url,
                json={"model": self._model, "prompt": prompt, "stream": False, "options": {"num_predict": 10}},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "0").strip()
            score = self._parse_score(raw)
            log.debug("LLM score for %s: %.2f", doc_id, score)
            return score
        except Exception as e:
            log.warning("LLM scoring falló para %s: %s", doc_id, e)
            return 0.0

    def _parse_score(self, raw: str) -> float:
        nums = re.findall(r"\d+\.?\d*", raw)
        if nums:
            val = float(nums[0])
            return min(val / 10.0, 1.0)
        return 0.0
