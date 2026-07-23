"""Tests para ReportingPlugin."""

from __future__ import annotations

from scripts.pro.tuneladora.engine import PipelineEngine
from scripts.pro.tuneladora.plugins.reporting import ReportingPlugin


def test_plugin_init():
    engine = PipelineEngine()
    plugin = ReportingPlugin(engine)
    assert plugin is not None
    assert plugin.engine is engine
