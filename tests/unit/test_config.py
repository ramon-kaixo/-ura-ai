"""Tests de config_manager y document_quality."""

from core.config_manager import CONFIG
from motor.core.config import UraConfig


def test_config_loads() -> None:
    assert CONFIG is not None
    assert isinstance(CONFIG, dict)


def test_config_has_rag() -> None:
    rag = CONFIG.get("rag", {})
    assert isinstance(rag, dict)


def test_config_has_paths() -> None:
    paths = CONFIG.get("paths", {})
    assert isinstance(paths, dict)


def test_uraconfig_consistency() -> None:
    """Verifica que los campos compartidos entre UraConfig y CONFIG coinciden."""
    cfg = UraConfig.load()
    assert cfg.data_dir == CONFIG["paths"]["data"], (
        f"data_dir mismatch: UraConfig={cfg.data_dir} != CONFIG={CONFIG['paths']['data']}"
    )
    assert cfg.log_level == CONFIG["log_level"], (
        f"log_level mismatch: UraConfig={cfg.log_level} != CONFIG={CONFIG['log_level']}"
    )
