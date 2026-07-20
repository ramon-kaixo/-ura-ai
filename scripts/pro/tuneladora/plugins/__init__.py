"""Plugins de mantenimiento para el PipelineEngine."""

from scripts.pro.tuneladora.plugins.health import HealthPlugin
from scripts.pro.tuneladora.plugins.code_quality import CodeQualityPlugin
from scripts.pro.tuneladora.plugins.cleanup import CleanupPlugin
from scripts.pro.tuneladora.plugins.reporting import ReportingPlugin

__all__ = ["HealthPlugin", "CodeQualityPlugin", "CleanupPlugin", "ReportingPlugin"]
