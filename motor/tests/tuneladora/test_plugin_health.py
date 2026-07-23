"""Tests para HealthPlugin."""

from __future__ import annotations

from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.tuneladora.plugins.health import HealthPlugin


def test_plugin_init():
    engine = PipelineEngine()
    plugin = HealthPlugin(engine)
    assert plugin is not None
    assert plugin.engine is engine


def test_check_all_returns_dict():
    engine = PipelineEngine()
    plugin = HealthPlugin(engine)
    result = plugin.check_all()
    assert isinstance(result, dict)
    assert "disco" in result
    assert "ollama" in result
