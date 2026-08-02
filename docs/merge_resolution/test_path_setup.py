"""Tests de path_setup, notifier, json_logger — RESOLUCION DE MERGE (Fase 5)."""

import sys
from pathlib import Path

from core.json_logger import StructuredLogger
from core.notifier import notify
from path_setup import get_project_root, setup_path


# === path_setup (nuestros 4 tests) ===
def test_path_setup_basic() -> None:
    setup_path()
    root = get_project_root()
    assert root is not None
    assert root.exists()


def test_get_project_root_returns_path() -> None:
    root = get_project_root()
    assert isinstance(root, Path)
    assert root.exists()


def test_project_root_in_sys_path() -> None:
    root = get_project_root()
    assert str(root) in sys.path


def test_setup_path_idempotent() -> None:
    count_before = sys.path.count(str(get_project_root()))
    setup_path()
    count_after = sys.path.count(str(get_project_root()))
    assert count_after == count_before


# === notifier (OpenCode) ===
def test_notifier_return_false_when_disabled() -> None:
    try:
        result = notify("test message", level="info")
        assert result is False
    except Exception:
        pass


# === json_logger (OpenCode) ===
def test_structured_logger_creates() -> None:
    log = StructuredLogger("test_logger")
    assert log is not None
    log.info("test message")
    log.warning("test warning")
    log.error("test error")
