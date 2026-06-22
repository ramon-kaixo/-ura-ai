
"""Tests de config_manager y document_quality."""
from core.config_manager import CONFIG


def test_config_loads():
    assert CONFIG is not None
    assert isinstance(CONFIG, dict)


def test_config_has_rag():
    rag = CONFIG.get("rag", {})
    assert isinstance(rag, dict)


def test_config_has_paths():
    paths = CONFIG.get("paths", {})
    assert isinstance(paths, dict)
