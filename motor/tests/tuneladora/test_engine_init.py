"""Tests para PipelineEngine."""

from __future__ import annotations

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.engine import PipelineEngine


def test_config_init():
    config = Configuration()
    assert config is not None
    assert config.ura_root.exists()


def test_engine_init():
    engine = PipelineEngine()
    assert engine is not None
    assert engine.config is not None
    assert engine.log is not None
    assert engine.ledger is not None
    assert engine.checkpoint is not None
    assert engine.promotion is not None


def test_engine_init_with_config():
    config = Configuration()
    engine = PipelineEngine(config=config, pipeline="test_pipeline")
    assert engine.config == config


def test_promotion_policy():
    engine = PipelineEngine()
    assert engine.promotion.can_promote is False
    engine.promotion.record("test_check", True, "OK")
    assert engine.promotion.can_promote is True
