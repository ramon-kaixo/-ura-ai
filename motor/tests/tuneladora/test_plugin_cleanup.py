"""Tests para CleanupPlugin."""

from __future__ import annotations

from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.tuneladora.plugins.cleanup import CleanupPlugin


def test_plugin_init():
    engine = PipelineEngine()
    plugin = CleanupPlugin(engine)
    assert plugin is not None


def test_watermark_returns_dict():
    engine = PipelineEngine()
    plugin = CleanupPlugin(engine)
    result = plugin.watermark()
    assert isinstance(result, dict)
