#!/usr/bin/env python3
"""Tests for ura_search.py — entry point unificado N1/N2/N3."""

from __future__ import annotations

import pytest

import ura_search
from core.ura_nivel_router import Nivel, RouterDecision


@pytest.mark.asyncio
async def test_unified_search_force_n3(monkeypatch):
    """Forzar N3 debe llamar al pipeline N3 sin pasar por el router."""
    captured = {}

    async def fake_n3(tema, contexto=None, learn=True, n2_runner=None):
        captured["tema_n3"] = tema
        captured["learn"] = learn
        return {"tema": tema, "estado": "ok", "resultados": [{"titulo": "A", "url": "u"}]}

    monkeypatch.setattr(ura_search.ura_n3_search, "n3_search", fake_n3)

    result = await ura_search.unified_search("tema X", force_level="N3")
    assert captured["tema_n3"] == "tema X"
    assert result["nivel_ejecutado"] == "N3"
    assert result["resultados"][0]["url"] == "u"


@pytest.mark.asyncio
async def test_unified_search_force_n2(monkeypatch):
    async def fake_n2(query, use_cache=True, max_results=10, **kw):
        return {
            "query": query,
            "results": [{"titulo": "B", "url": "u2"}],
            "by_agent": {},
            "errors": {},
            "agents_used": [],
            "duplicates_removed": 0,
            "cache_hit": False,
        }

    monkeypatch.setattr(ura_search.ura_n2_search, "n2_search", fake_n2)

    result = await ura_search.unified_search("tema Y", force_level="N2")
    assert result["nivel_ejecutado"] == "N2"
    assert result["resultados"][0]["url"] == "u2"


@pytest.mark.asyncio
async def test_unified_search_router_decides_n2(monkeypatch):
    """Si el router decide N2, debe ejecutarse el pipeline N2."""
    fake_decision = RouterDecision(
        nivel=Nivel.N2,
        maleta_id="mtest",
        confianza=0.9,
        uses=5,
        razon="alta",
    )

    class _FakeRouter:
        async def decide(self, tema, **kw):
            return fake_decision

        async def record_execution(self, mid):
            pass

    monkeypatch.setattr(ura_search, "get_router", lambda: _FakeRouter())

    async def fake_n2(query, use_cache=True, max_results=10, **kw):
        return {
            "query": query,
            "results": [{"url": "n2-url"}],
            "cache_hit": False,
            "agents_used": [],
            "errors": {},
            "by_agent": {},
            "duplicates_removed": 0,
        }

    monkeypatch.setattr(ura_search.ura_n2_search, "n2_search", fake_n2)

    result = await ura_search.unified_search("tema Z")
    assert result["decision"]["nivel"] == "N2"
    assert result["nivel_ejecutado"] == "N2"


@pytest.mark.asyncio
async def test_unified_search_n2_n3_returns_n2_first(monkeypatch):
    fake_decision = RouterDecision(
        nivel=Nivel.N2_N3,
        maleta_id="mtest",
        confianza=0.7,
        uses=2,
        razon="media",
    )

    class _FakeRouter:
        async def decide(self, tema, **kw):
            return fake_decision

        async def record_execution(self, mid):
            pass

    monkeypatch.setattr(ura_search, "get_router", lambda: _FakeRouter())

    async def fake_n2(query, use_cache=True, max_results=10, **kw):
        return {
            "query": query,
            "results": [{"url": "n2"}],
            "cache_hit": False,
            "agents_used": [],
            "errors": {},
            "by_agent": {},
            "duplicates_removed": 0,
        }

    monkeypatch.setattr(ura_search.ura_n2_search, "n2_search", fake_n2)

    async def fake_n3_slow(tema, contexto=None, learn=True, n2_runner=None):
        import asyncio

        await asyncio.sleep(5)  # más que el timeout (2s) de espera
        return {"tema": tema, "estado": "ok", "resultados": []}

    monkeypatch.setattr(ura_search.ura_n3_search, "n3_search", fake_n3_slow)

    result = await ura_search.unified_search("tema mid")
    assert result["nivel_ejecutado"] == "N2+N3"
    assert result["resultados"][0]["url"] == "n2"
    # N3 quedó en estado background
    assert result["n3"].get("estado") == "background"


def test_parse_level_valid():
    assert ura_search._parse_level("N2") == Nivel.N2
    assert ura_search._parse_level("n3") == Nivel.N3
    assert ura_search._parse_level("N2+N3") == Nivel.N2_N3


def test_parse_level_invalid():
    with pytest.raises(ValueError):
        ura_search._parse_level("X9")
