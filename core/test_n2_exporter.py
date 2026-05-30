#!/usr/bin/env python3
"""Tests for core/ura_n2_to_n8n_exporter.py (N2 Fase 4 stub)."""

from __future__ import annotations

import json

import pytest

from core.ura_n2_to_n8n_exporter import N2ToN8nExporter


def _mature_maleta() -> dict:
    return {
        "maleta_id": "fiscal_v9",
        "version": 3,
        "confianza": 0.97,
        "tema": "fiscalidad",
        "herramientas": {
            "buscadores": [{"nombre": "x"}],
            "validadores": [{"nombre": "head_check"}],
        },
        "formato_salida": {"estructura": {}},
    }


def test_is_eligible_passes_for_mature_maleta():
    exp = N2ToN8nExporter()
    assert exp.is_eligible(_mature_maleta(), uses=25) is True


def test_is_eligible_fails_for_low_uses():
    exp = N2ToN8nExporter()
    assert exp.is_eligible(_mature_maleta(), uses=5) is False


def test_is_eligible_fails_for_low_confidence():
    exp = N2ToN8nExporter()
    m = _mature_maleta()
    m["confianza"] = 0.7
    assert exp.is_eligible(m, uses=30) is False


def test_is_eligible_fails_when_no_validadores():
    exp = N2ToN8nExporter()
    m = _mature_maleta()
    m["herramientas"]["validadores"] = []
    assert exp.is_eligible(m, uses=30) is False


def test_build_workflow_skeleton():
    exp = N2ToN8nExporter()
    wf = exp.build_workflow_json(_mature_maleta())
    assert wf["meta"]["maleta_id"] == "fiscal_v9"
    assert wf["active"] is False
    assert "nodes" in wf
    assert "connections" in wf


@pytest.mark.asyncio
async def test_export_writes_local_json(tmp_path):
    exp = N2ToN8nExporter(export_dir=tmp_path / "out")
    result = await exp.export(_mature_maleta(), uses=25)
    assert result.ok is True
    assert result.workflow_json_path.exists()
    payload = json.loads(result.workflow_json_path.read_text(encoding="utf-8"))
    assert payload["meta"]["maleta_id"] == "fiscal_v9"


@pytest.mark.asyncio
async def test_export_rejects_ineligible(tmp_path):
    exp = N2ToN8nExporter(export_dir=tmp_path / "out")
    m = _mature_maleta()
    m["confianza"] = 0.4
    result = await exp.export(m, uses=2)
    assert result.ok is False
    assert result.errores
