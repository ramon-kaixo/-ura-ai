"""Tests para CodeQualityPlugin."""

from __future__ import annotations

from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.tuneladora.plugins.code_quality import CodeQualityPlugin


def test_plugin_init():
    engine = PipelineEngine()
    plugin = CodeQualityPlugin(engine)
    assert plugin is not None
    assert plugin.engine is engine


def test_ruff_check_returns_dict():
    engine = PipelineEngine()
    plugin = CodeQualityPlugin(engine)
    result = plugin.ruff_check()
    assert isinstance(result, dict)
    assert "f821" in result
    assert "f841" in result
