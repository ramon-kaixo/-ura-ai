"""Tests for path_setup.py."""

import sys
from pathlib import Path

import pytest

from path_setup import get_project_root, setup_path


class TestPathSetup:
    def test_setup_path_no_crash(self):
        setup_path()

    def test_get_project_root_returns_path(self):
        root = get_project_root()
        assert isinstance(root, Path)
        assert root.exists()

    def test_project_root_in_sys_path(self):
        root = get_project_root()
        assert str(root) in sys.path

    def test_setup_path_idempotent(self):
        count_before = sys.path.count(str(get_project_root()))
        setup_path()
        count_after = sys.path.count(str(get_project_root()))
        assert count_after == count_before
