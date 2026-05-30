#!/usr/bin/env python3
"""Tests for core/ura_openclaw_client.py — sin tocar el binario real."""

from __future__ import annotations


import pytest

from core.ura_openclaw_client import (
    OpenClawAvailability,
    OpenClawClient,
    detect_openclaw,
)


def test_detect_with_stub_env(monkeypatch):
    monkeypatch.setenv("URA_OPENCLAW_STUB", "1")
    monkeypatch.delenv("URA_OPENCLAW_HTTP", raising=False)
    avail = detect_openclaw()
    assert avail.mode == "stub"


def test_detect_with_http_env(monkeypatch):
    monkeypatch.delenv("URA_OPENCLAW_STUB", raising=False)
    monkeypatch.setenv("URA_OPENCLAW_HTTP", "http://localhost:9999")
    avail = detect_openclaw()
    assert avail.mode == "http"
    assert avail.http_url == "http://localhost:9999"


@pytest.mark.asyncio
async def test_stub_mode_returns_normalized_payload():
    avail = OpenClawAvailability(mode="stub", reason="forced for test")
    client = OpenClawClient(availability=avail)
    payload = await client.search("tema X")
    assert payload["nivel"] == "N3"
    assert payload["estado"] == "stub_noop"
    assert payload["resultados"] == []
    assert "duracion_segundos" in payload


@pytest.mark.asyncio
async def test_normalize_handles_missing_keys():
    avail = OpenClawAvailability(mode="stub")
    client = OpenClawClient(availability=avail)
    out = client._normalize("tema", {"reasoning": "x", "results": [{"title": "T", "url": "u"}]})
    assert out["razonamiento"] == "x"
    assert out["resultados"][0]["titulo"] == "T"
    assert out["resultados"][0]["url"] == "u"


@pytest.mark.asyncio
async def test_normalize_handles_string_input():
    avail = OpenClawAvailability(mode="stub")
    client = OpenClawClient(availability=avail)
    out = client._normalize("tema", "respuesta libre")
    assert out["raw"]["text"] == "respuesta libre"
    assert out["estado"] == "ok"


@pytest.mark.asyncio
async def test_subprocess_mode_handles_failure(monkeypatch, tmp_path):
    """Si el binario no existe, el subprocess falla y la excepción debe convertirse en estado=error."""
    # Ruta inválida
    fake_bin = str(tmp_path / "nonexistent_openclaw")
    avail = OpenClawAvailability(mode="subprocess", binary_path=fake_bin)
    client = OpenClawClient(availability=avail)
    payload = await client.search("tema")
    assert payload["estado"] == "error"
    assert "error" in payload


def test_reset_makes_redetection_possible(monkeypatch):
    from core import ura_openclaw_client as mod

    mod._client = None
    c1 = mod.get_openclaw_client()
    c2 = mod.get_openclaw_client()
    assert c1 is c2
    mod.reset_openclaw_client()
    c3 = mod.get_openclaw_client()
    assert c3 is not c1
