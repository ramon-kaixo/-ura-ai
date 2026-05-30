#!/usr/bin/env python3
"""Tests for ura_n2_search.py (entry point CLI/API)."""

from __future__ import annotations


import pytest

from core.buscadores.base import BaseSearchAgent, SearchAgentMeta
from core.buscadores.orchestrator import SearchOrchestrator
import ura_n2_search


class _FakeAgent(BaseSearchAgent):
    META = SearchAgentMeta(nombre="fake")

    def search(self, query: str, max_results: int = 10):
        return [
            {
                "titulo": "Resultado",
                "url": "https://x.com/r",
                "snippet": "demo",
                "score_relevancia": 0.7,
            },
        ]


@pytest.mark.asyncio
async def test_n2_search_returns_payload(tmp_path, monkeypatch):
    # Patch cache to use temp DB
    from core.ura_search_cache import SearchCache

    cache = SearchCache(db_path=tmp_path / "c.db")
    monkeypatch.setattr(ura_n2_search, "get_search_cache", lambda: cache)

    # Patch orchestrator to use only the fake agent
    fake_orch = SearchOrchestrator(agent_classes=[_FakeAgent])
    monkeypatch.setattr(ura_n2_search, "get_orchestrator", lambda: fake_orch)

    payload = await ura_n2_search.n2_search("una query test", use_cache=True)
    assert payload["query"] == "una query test"
    assert payload["cache_hit"] is False
    assert len(payload["results"]) == 1
    assert payload["results"][0]["url"] == "https://x.com/r"


@pytest.mark.asyncio
async def test_n2_search_uses_cache_on_second_call(tmp_path, monkeypatch):
    from core.ura_search_cache import SearchCache

    cache = SearchCache(db_path=tmp_path / "c.db")
    monkeypatch.setattr(ura_n2_search, "get_search_cache", lambda: cache)

    fake_orch = SearchOrchestrator(agent_classes=[_FakeAgent])
    monkeypatch.setattr(ura_n2_search, "get_orchestrator", lambda: fake_orch)

    p1 = await ura_n2_search.n2_search("repetida")
    p2 = await ura_n2_search.n2_search("repetida")
    assert p1["cache_hit"] is False
    assert p2["cache_hit"] is True


@pytest.mark.asyncio
async def test_n2_search_no_cache_flag(tmp_path, monkeypatch):
    from core.ura_search_cache import SearchCache

    cache = SearchCache(db_path=tmp_path / "c.db")
    monkeypatch.setattr(ura_n2_search, "get_search_cache", lambda: cache)

    fake_orch = SearchOrchestrator(agent_classes=[_FakeAgent])
    monkeypatch.setattr(ura_n2_search, "get_orchestrator", lambda: fake_orch)

    p1 = await ura_n2_search.n2_search("sin cache", use_cache=False)
    p2 = await ura_n2_search.n2_search("sin cache", use_cache=False)
    assert p1["cache_hit"] is False
    assert p2["cache_hit"] is False


def test_avg_score_empty_returns_zero():
    assert ura_n2_search._avg_score([]) == 0.0


def test_avg_score_computes_mean():
    avg = ura_n2_search._avg_score([{"score_relevancia": 0.4}, {"score_relevancia": 0.6}])
    assert abs(avg - 0.5) < 0.01


def test_cli_args_parser_basic():
    args = ura_n2_search._parse_args(["alguna query", "--max-results", "5"])
    assert args.query == "alguna query"
    assert args.max_results == 5
    assert args.no_cache is False


def test_cli_args_parser_json_no_cache():
    args = ura_n2_search._parse_args(["q", "--json", "--no-cache"])
    assert args.json is True
    assert args.no_cache is True
