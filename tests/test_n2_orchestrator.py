#!/usr/bin/env python3
"""Tests for core/buscadores/orchestrator.py and core/buscadores/base.py."""

from __future__ import annotations


import pytest

from core.buscadores.base import BaseSearchAgent, SearchAgentMeta
from core.buscadores.orchestrator import OrchestratorReport, SearchOrchestrator

# ---------------------------------------------------------------- Fakes ------


class _FakeAgentNoticias(BaseSearchAgent):
    META = SearchAgentMeta(
        nombre="fake_noticias",
        keywords_disparadoras=["noticia", "news"],
    )

    def search(self, query: str, max_results: int = 10):
        return [
            {
                "titulo": "Noticia A",
                "url": "https://x.com/a",
                "snippet": "alpha",
                "score_relevancia": 0.9,
            },
            {
                "titulo": "Noticia B",
                "url": "https://x.com/b",
                "snippet": "beta",
                "score_relevancia": 0.6,
            },
        ]


class _FakeAgentEstudios(BaseSearchAgent):
    META = SearchAgentMeta(
        nombre="fake_estudios",
        keywords_disparadoras=["paper", "estudio"],
    )

    def search(self, query: str, max_results: int = 10):
        return [
            # Misma URL que la primera de Noticias — debe ser deduplicada
            {
                "titulo": "Noticia A duplicada",
                "url": "https://x.com/a",
                "snippet": "alpha",
                "score_relevancia": 0.5,
            },
            {
                "titulo": "Estudio C",
                "url": "https://x.com/c",
                "snippet": "gamma",
                "score_relevancia": 0.8,
            },
        ]


class _FakeAgentVacio(BaseSearchAgent):
    META = SearchAgentMeta(nombre="fake_vacio")

    def search(self, query: str, max_results: int = 10):
        return []


class _FakeAgentError(BaseSearchAgent):
    META = SearchAgentMeta(nombre="fake_error")

    def search(self, query: str, max_results: int = 10):
        raise RuntimeError("simulated")


# --------------------------------------------------------- Base helpers ------


def test_base_normalize_result_legacy_keys():
    out = BaseSearchAgent.normalize_result(
        {"title": "T", "link": "https://l", "body": "abc", "date": "2024-01-01"},
        fuente_default="X",
    )
    assert out["titulo"] == "T"
    assert out["url"] == "https://l"
    assert out["snippet"] == "abc"
    assert out["fecha"] == "2024-01-01"
    assert out["fuente"] == "X"
    assert 0.0 <= out["score_relevancia"] <= 1.0


def test_base_acepta_query_keyword_match():
    assert _FakeAgentNoticias.acepta_query("dame noticias de hoy")
    assert not _FakeAgentNoticias.acepta_query("paper de arxiv")


def test_base_acepta_query_no_keywords_means_always():
    assert _FakeAgentVacio.acepta_query("cualquier cosa") is True


# --------------------------------------------------- Orchestrator selection --


def test_select_agents_filters_by_keyword():
    orch = SearchOrchestrator(
        agent_classes=[_FakeAgentNoticias, _FakeAgentEstudios, _FakeAgentVacio]
    )
    selected = orch.select_agents("dame noticias urgentes")
    names = {c.__name__ for c in selected}
    # FakeNoticias acepta y FakeVacio acepta siempre
    assert "_FakeAgentNoticias" in names
    assert "_FakeAgentVacio" in names
    assert "_FakeAgentEstudios" not in names


def test_select_agents_no_match_falls_back_to_all():
    orch = SearchOrchestrator(agent_classes=[_FakeAgentNoticias, _FakeAgentEstudios])
    selected = orch.select_agents("texto sin keywords")
    assert len(selected) == 2


# --------------------------------------------------- Orchestrator search -----


@pytest.mark.asyncio
async def test_search_paralelo_retorna_resultados():
    orch = SearchOrchestrator(agent_classes=[_FakeAgentNoticias, _FakeAgentEstudios])
    report = await orch.search("noticia paper")
    assert isinstance(report, OrchestratorReport)
    # 4 raw → 1 dedupe por URL → 3
    assert len(report.results) == 3
    assert report.duplicates_removed == 1
    assert "_FakeAgentNoticias" in report.by_agent
    assert "_FakeAgentEstudios" in report.by_agent


@pytest.mark.asyncio
async def test_search_dedup_por_similitud():
    """Dos resultados con mismo signature pero distinta URL → deduplicado."""

    class _AgentSimA(BaseSearchAgent):
        META = SearchAgentMeta(nombre="a")

        def search(self, q, m=10):
            return [
                {
                    "titulo": "Lo mismo",
                    "url": "https://a.com",
                    "snippet": "Idéntico contenido",
                    "score_relevancia": 0.7,
                }
            ]

    class _AgentSimB(BaseSearchAgent):
        META = SearchAgentMeta(nombre="b")

        def search(self, q, m=10):
            return [
                {
                    "titulo": "Lo mismo",
                    "url": "https://b.com",
                    "snippet": "Idéntico contenido",
                    "score_relevancia": 0.6,
                }
            ]

    orch = SearchOrchestrator(agent_classes=[_AgentSimA, _AgentSimB], sim_threshold=0.9)
    report = await orch.search("query")
    assert report.duplicates_removed == 1
    assert len(report.results) == 1


@pytest.mark.asyncio
async def test_search_handles_agent_errors():
    orch = SearchOrchestrator(agent_classes=[_FakeAgentNoticias, _FakeAgentError])
    report = await orch.search("noticia")
    assert "_FakeAgentError" in report.errors
    assert "RuntimeError" in report.errors["_FakeAgentError"]
    assert any(r["titulo"].startswith("Noticia") for r in report.results)


@pytest.mark.asyncio
async def test_search_ranks_by_score():
    orch = SearchOrchestrator(agent_classes=[_FakeAgentNoticias, _FakeAgentEstudios])
    report = await orch.search("noticia paper")
    scores = [r["score_relevancia"] for r in report.results]
    assert scores == sorted(scores, reverse=True)
