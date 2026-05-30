#!/usr/bin/env python3
"""Tests for core/ura_nivel_router.py (N2 Fase 2)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, UTC

import pytest

from core.ura_maleta_manager import Maleta, MaletaManager
from core.ura_nivel_router import (
    Nivel,
    NivelRouter,
    UsageStore,
    UsageStats,
    apply_decay,
    lanzar_n3_background,
)


def _mk_data(maleta_id: str, conf: float, tema: str = "tema test") -> dict:
    return {
        "maleta_id": maleta_id,
        "version": 1,
        "creada_por": "manual",
        "fecha_creacion": "2026-05-05T00:00:00+00:00",
        "ultimo_uso": None,
        "confianza": conf,
        "tema": tema,
        "herramientas": {"buscadores": [{"nombre": "duckduckgo_text"}]},
        "formato_salida": {"estructura": {}},
    }


# ----------------------------------------------------------- classification ---


def test_classify_low_conf_routes_to_n3():
    nivel, _, _ = NivelRouter._classify(0.3, 0)
    assert nivel == Nivel.N3


def test_classify_mid_conf_routes_to_n2_n3():
    nivel, _, _ = NivelRouter._classify(0.7, 5)
    assert nivel == Nivel.N2_N3


def test_classify_high_conf_routes_to_n2():
    nivel, _, _ = NivelRouter._classify(0.9, 5)
    assert nivel == Nivel.N2


def test_classify_mature_suggests_n1():
    nivel, razon, sugs = NivelRouter._classify(0.96, 21)
    assert nivel == Nivel.N2
    assert any("n8n" in s.lower() for s in sugs)


# ----------------------------------------------------------------- decay ------


def test_apply_decay_no_history_unchanged(tmp_path):
    data = _mk_data("m1", 0.8)
    maleta = Maleta(maleta_id="m1", tema=data["tema"], data=data)
    stats = UsageStats(maleta_id="m1")
    new = apply_decay(maleta, stats)
    assert new == 0.8


def test_apply_decay_recent_use_unchanged():
    data = _mk_data("m1", 0.8)
    maleta = Maleta(maleta_id="m1", tema=data["tema"], data=data)
    stats = UsageStats(
        maleta_id="m1",
        last_used=(datetime.now(UTC) - timedelta(days=10)).isoformat(),
    )
    new = apply_decay(maleta, stats)
    assert new == 0.8


def test_apply_decay_stale_reduces_confidence():
    data = _mk_data("m1", 0.8)
    maleta = Maleta(maleta_id="m1", tema=data["tema"], data=data)
    # 4 months stale → ~3 monthly decay applied (after 90-day grace)
    stats = UsageStats(
        maleta_id="m1",
        last_used=(datetime.now(UTC) - timedelta(days=180)).isoformat(),
    )
    new = apply_decay(maleta, stats)
    assert new < 0.8
    assert new >= 0.0


# ---------------------------------------------------------- usage store -------


@pytest.mark.asyncio
async def test_usage_store_records_uses(tmp_path):
    store = UsageStore(path=tmp_path / "usage.json")
    await store.record_use("m1")
    await store.record_use("m1")
    await store.record_use("m2")
    snap = await store.snapshot()
    assert snap["m1"].uses == 2
    assert snap["m2"].uses == 1


@pytest.mark.asyncio
async def test_usage_store_persists(tmp_path):
    path = tmp_path / "usage.json"
    store1 = UsageStore(path=path)
    await store1.record_use("m1")
    # New instance reads from disk
    store2 = UsageStore(path=path)
    snap = await store2.snapshot()
    assert snap["m1"].uses == 1


# ---------------------------------------------------------------- decide ------


@pytest.mark.asyncio
async def test_decide_no_maleta_returns_n3(tmp_path, monkeypatch):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    monkeypatch.setattr("core.ura_nivel_router.get_maleta_manager", lambda: mgr)
    router = NivelRouter(usage_store=UsageStore(path=tmp_path / "u.json"))
    router.maleta_mgr = mgr  # ensure direct reference
    decision = await router.decide("tema desconocido", allow_clone=False)
    assert decision.nivel == Nivel.N3
    assert decision.maleta_id is None


@pytest.mark.asyncio
async def test_decide_with_explicit_high_conf(tmp_path, monkeypatch):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    data = _mk_data("hi_v1", 0.9, "fiscalidad autónomos")
    mgr.save(Maleta(maleta_id="hi_v1", tema=data["tema"], data=data))
    monkeypatch.setattr("core.ura_nivel_router.get_maleta_manager", lambda: mgr)

    router = NivelRouter(usage_store=UsageStore(path=tmp_path / "u.json"))
    router.maleta_mgr = mgr
    decision = await router.decide("cualquier tema", maleta_id="hi_v1")
    assert decision.nivel == Nivel.N2
    assert decision.maleta_id == "hi_v1"
    assert decision.confianza == 0.9


@pytest.mark.asyncio
async def test_decide_low_conf_routes_to_n3(tmp_path, monkeypatch):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    data = _mk_data("lo_v1", 0.3, "tema pobre")
    mgr.save(Maleta(maleta_id="lo_v1", tema=data["tema"], data=data))
    monkeypatch.setattr("core.ura_nivel_router.get_maleta_manager", lambda: mgr)

    router = NivelRouter(usage_store=UsageStore(path=tmp_path / "u.json"))
    router.maleta_mgr = mgr
    decision = await router.decide("tema pobre", maleta_id="lo_v1")
    assert decision.nivel == Nivel.N3


@pytest.mark.asyncio
async def test_record_execution_increments(tmp_path, monkeypatch):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    monkeypatch.setattr("core.ura_nivel_router.get_maleta_manager", lambda: mgr)
    router = NivelRouter(usage_store=UsageStore(path=tmp_path / "u.json"))
    await router.record_execution("xx")
    await router.record_execution("xx")
    snap = await router.usage.snapshot()
    assert snap["xx"].uses == 2


# ----------------------------------------------------------- N3 launcher ------


@pytest.mark.asyncio
async def test_lanzar_n3_background_stub_resolves():
    task = await lanzar_n3_background("tema X")
    result = await task
    assert result["nivel"] == "N3"
    assert result["estado"] == "stub_noop"


@pytest.mark.asyncio
async def test_lanzar_n3_background_with_real_fn():
    async def fake_openclaw(tema: str) -> dict:
        return {"tema": tema, "nivel": "N3", "estado": "ok", "resultados": [{"x": 1}]}

    seen = []

    async def cb(result):
        seen.append(result)

    task = await lanzar_n3_background("tema Y", openclaw_fn=fake_openclaw, on_complete=cb)
    result = await task
    assert result["estado"] == "ok"
    # callback called
    await asyncio.sleep(0.01)
    assert seen and seen[0]["estado"] == "ok"
