#!/usr/bin/env python3
"""Tests for core/ura_n2_validador.py (N2 Fase 1)."""

from __future__ import annotations

import pytest

from core.ura_n2_validador import (
    consolidate_sources,
    detect_contradictions,
    quality_score,
    validate_swarm_output,
)


def test_quality_score_zero_results_is_zero():
    assert quality_score(0, 0.0, [], 0) == 0.0


def test_quality_score_clean():
    s = quality_score(10, 1.0, [], 0)
    assert s > 0.9


def test_quality_score_penalizes_contradictions():
    clean = quality_score(10, 1.0, [], 0)
    bad = quality_score(10, 1.0, [{}, {}, {}], 0)
    assert bad < clean


def test_detect_contradictions_flags_opposing_stances():
    resultados = [
        {
            "agente_id": "a1",
            "resultados": [
                {"titulo": "Impuesto autónomos es legal", "resumen": "está permitido"},
            ],
        },
        {
            "agente_id": "a2",
            "resultados": [
                {"titulo": "Impuesto autónomos es ilegal", "resumen": "está prohibido"},
            ],
        },
    ]
    contra = detect_contradictions(resultados)
    assert len(contra) >= 1


def test_consolidate_sources_counts_agents():
    resultados = [
        {"agente_id": "a1", "resultados": [{"url": "https://x.com", "titulo": "T"}]},
        {"agente_id": "a2", "resultados": [{"url": "https://x.com", "titulo": "T"}]},
        {"agente_id": "a3", "resultados": [{"url": "https://y.com", "titulo": "Y"}]},
    ]
    cons = consolidate_sources(resultados)
    top = cons[0]
    assert top["url"] == "https://x.com"
    assert top["count"] == 2
    assert set(top["cited_by"]) == {"a1", "a2"}


@pytest.mark.asyncio
async def test_validate_swarm_output_no_aiohttp_optimistic(monkeypatch):
    """Even without aiohttp it must return a sensible structure."""
    # Force the optimistic path by pretending aiohttp is absent inside validate_urls
    import core.ura_n2_validador as mod

    async def fake_validate_urls(urls, timeout_s=5):
        return {u: {"ok": True, "status": 200} for u in urls}

    monkeypatch.setattr(mod, "validate_urls", fake_validate_urls)

    resultados = [
        {
            "agente_id": "a1",
            "estado": "ok",
            "resultados": [{"url": "https://ok.com", "titulo": "Ok"}],
        }
    ]
    out = await validate_swarm_output(resultados)
    assert "score_calidad" in out
    assert out["alive_urls_ratio"] == 1.0
