#!/usr/bin/env python3
"""Tests for core/buscadores_adapter.py (N2 Fase 2)."""

from __future__ import annotations

import asyncio

import pytest

from core.buscadores_adapter import (
    AGENT_REGISTRY,
    _normalize_result,
    buscadores_agent_factory,
    list_available_roles,
)


def test_registry_has_six_roles():
    roles = list_available_roles()
    assert set(roles) == {
        "noticias",
        "estudios",
        "aplicaciones",
        "documentacion",
        "manuales",
        "tendencias",
    }


def test_normalize_result_maps_legacy_keys():
    raw = {"title": "X", "link": "https://y", "body": "abc", "date": "2024-01-01"}
    out = _normalize_result(raw, "noticias")
    assert out["titulo"] == "X"
    assert out["url"] == "https://y"
    assert out["resumen"] == "abc"
    assert out["fecha"] == "2024-01-01"
    assert out["fuente_tipo"] == "noticias"


def test_factory_known_role_picks_correct_fn():
    spec = buscadores_agent_factory("subtema X", "noticias", {"maleta_id": "m"})
    assert spec.rol == "noticias"
    assert spec.fn is AGENT_REGISTRY["noticias"]
    assert spec.subtema == "subtema X"


def test_factory_unknown_role_falls_back_to_default():
    spec = buscadores_agent_factory(
        "subtema Z",
        "rol_desconocido",
        {"maleta_id": "m", "tema": "x", "herramientas": {"buscadores": [{"nombre": "x"}]}},
    )
    # default factory generates an agent_id starting with "agent_"
    assert spec.agent_id.startswith("agent_")


@pytest.mark.asyncio
async def test_each_agent_function_returns_list(monkeypatch):
    """Smoke test: every adapter returns a list (may be empty if buscador hits net errors)."""
    for rol, fn in AGENT_REGISTRY.items():
        try:
            result = await asyncio.wait_for(fn("tema test", {}), timeout=20)
        except TimeoutError:
            pytest.skip(f"buscador {rol} demasiado lento — entorno sin red")
        assert isinstance(result, list), f"{rol} no devolvió lista"
