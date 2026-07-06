"""LLMFactExtractor — extracción de hechos mediante LLM (Ollama)."""

from __future__ import annotations

import json
import logging
import time

import httpx

from motor.intelligence.memory.episodic import Episode
from motor.intelligence.memory.extractor import FactExtractor
from motor.intelligence.memory.semantic import SemanticFact

log = logging.getLogger("ura.extractor.llm")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:7b"


class LLMFactExtractor(FactExtractor):
    def __init__(
        self,
        model: str = MODEL,
        ollama_url: str = OLLAMA_URL,
        timeout: int = 30,
    ) -> None:
        self._model = model
        self._url = ollama_url
        self._timeout = timeout

    def extract(self, episode: Episode) -> list[SemanticFact]:
        if not episode.payload:
            return []
        prompt = self._build_prompt(episode.payload)
        start = time.monotonic()
        try:
            resp = httpx.post(
                self._url,
                json={"model": self._model, "prompt": prompt, "stream": False, "options": {"num_predict": 500}},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            elapsed = (time.monotonic() - start) * 1000
            raw = data.get("response", "[]")
            facts = self._parse_response(raw, episode)
            log.debug("LLM extracted %d facts from episode %s (%.0fms)", len(facts), episode.id[:8], elapsed)
            return facts
        except Exception as exc:
            log.warning("LLM extraction failed for %s: %s", episode.id[:8], exc)
            return []

    def _build_prompt(self, text: str) -> str:
        return (
            f"Extract facts from the following text as a JSON array. "
            f"Each fact must have 'subject', 'predicate', 'object', and 'type' "
            f"(one of: attribute, relation, event, error, statement).\n\n"
            f"Text: {text[:2000]}\n\n"
            f"JSON:"
        )

    def _parse_response(self, raw: str, episode: Episode) -> list[SemanticFact]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            items = self._fallback_parse(raw)

        if not isinstance(items, list):
            return []

        facts: list[SemanticFact] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            fact = SemanticFact(
                subject=str(item.get("subject", "unknown")),
                predicate=str(item.get("predicate", "is")),
                object_value=str(item.get("object", "")),
                fact_type=str(item.get("type", "statement")),
                source_episode_ids=[episode.id],
                tags=list(episode.tags),
                metadata={"session_id": episode.session_id},
                confidence=episode.confidence * 0.8,
                importance=episode.importance,
            )
            if fact.subject and fact.object_value:
                facts.append(fact)

        return facts

    def _fallback_parse(self, raw: str) -> list[dict]:
        import re
        items: list[dict] = []
        for match in re.finditer(r"\{\s*\"subject\"\s*:\s*\"([^\"]+)\"", raw):
            items.append({"subject": match.group(1)})
        return items
