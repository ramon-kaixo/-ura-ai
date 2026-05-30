#!/usr/bin/env python3
"""Tests for core/ura_swarm_local.py (N2 Fase 1).

These tests use a fake agent so they run offline / deterministically.
"""

from __future__ import annotations

import asyncio

import pytest

from core.ura_swarm_local import AgentSpec, URASwarm, _split_tema

pytestmark = pytest.mark.asyncio


def _make_maleta(num=3, subtemas=None):
    return {
        "maleta_id": "fake_v1",
        "version": 1,
        "tema": "algo",
        "herramientas": {"buscadores": [{"nombre": "fake"}]},
        "formato_salida": {"estructura": {}},
        "division_subtemas": {
            "num_agentes_sugerido": num,
            "subtemas_explicitos": subtemas,
        },
    }


def _fake_factory_builder(
    delay: float = 0.01, should_fail: bool = False, results_per_agent: int = 2
):
    """Return a factory that produces deterministic fake agents."""
    import uuid

    async def fake_search(subtema, maleta):
        await asyncio.sleep(delay)
        if should_fail:
            raise RuntimeError("simulated failure")
        return [
            {
                "titulo": f"T_{subtema}_{i}",
                "url": f"https://example.com/{subtema.replace(' ', '_')}/{i}",
                "resumen": "ejemplo",
                "fuente_tipo": "web",
                "confianza": 0.7,
            }
            for i in range(results_per_agent)
        ]

    def factory(subtema, rol, maleta):
        return AgentSpec(
            agent_id=f"agent_{uuid.uuid4().hex[:6]}",
            rol=rol,
            subtema=subtema,
            fn=fake_search,
            maleta=maleta,
        )

    return factory


async def test_split_tema_explicit_subtemas():
    maleta = _make_maleta(num=2, subtemas=["sub1", "sub2", "sub3"])
    subs = _split_tema("ignored", maleta)
    assert subs == ["sub1", "sub2"]


async def test_split_tema_fallback_variants():
    maleta = _make_maleta(num=3)
    subs = _split_tema("fiscalidad", maleta)
    assert len(subs) == 3
    assert subs[0] == "fiscalidad"


async def test_swarm_runs_fake_agents_without_cache(monkeypatch, tmp_path):
    from core.ura_search_cache import SearchCache

    # Swap singleton cache to a temp one
    temp_cache = SearchCache(db_path=tmp_path / "cache.db")

    async def fake_validate_urls(urls, timeout_s=5):
        return {u: {"ok": True, "status": 200} for u in urls}

    import core.ura_n2_validador as val_mod

    monkeypatch.setattr(val_mod, "validate_urls", fake_validate_urls)

    swarm = URASwarm()
    swarm.cache = temp_cache

    maleta = _make_maleta(num=3)
    result = await swarm.run(
        tema="tema test",
        maleta=maleta,
        agent_factory=_fake_factory_builder(),
        use_cache=False,
    )
    assert result["exito"] is True
    assert len(result["resultados_por_agente"]) == 3
    assert result["score_calidad"] > 0.0
    assert result["cache_usado"] is False


async def test_swarm_uses_cache_on_second_run(monkeypatch, tmp_path):
    from core.ura_search_cache import SearchCache
    import core.ura_n2_validador as val_mod

    async def fake_validate_urls(urls, timeout_s=5):
        return {u: {"ok": True, "status": 200} for u in urls}

    monkeypatch.setattr(val_mod, "validate_urls", fake_validate_urls)

    temp_cache = SearchCache(db_path=tmp_path / "cache.db")
    swarm = URASwarm()
    swarm.cache = temp_cache

    maleta = _make_maleta(num=2)
    r1 = await swarm.run(tema="t", maleta=maleta, agent_factory=_fake_factory_builder())
    r2 = await swarm.run(tema="t", maleta=maleta, agent_factory=_fake_factory_builder())

    assert r1["cache_usado"] is False
    assert r2["cache_usado"] is True


async def test_swarm_handles_agent_errors(monkeypatch, tmp_path):
    from core.ura_search_cache import SearchCache
    import core.ura_n2_validador as val_mod

    async def fake_validate_urls(urls, timeout_s=5):
        return {u: {"ok": True, "status": 200} for u in urls}

    monkeypatch.setattr(val_mod, "validate_urls", fake_validate_urls)

    temp_cache = SearchCache(db_path=tmp_path / "cache.db")
    swarm = URASwarm()
    swarm.cache = temp_cache

    maleta = _make_maleta(num=2)
    result = await swarm.run(
        tema="t2",
        maleta=maleta,
        agent_factory=_fake_factory_builder(should_fail=True),
        use_cache=False,
    )
    # Agents fail → all report error, score low, exito False
    assert result["exito"] is False
    for ar in result["resultados_por_agente"]:
        assert ar["estado"] == "error"
        assert ar["errores"]
