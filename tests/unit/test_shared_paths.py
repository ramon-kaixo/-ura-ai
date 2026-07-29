"""Tests for shared/paths.py — canonical path definitions."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from shared.paths import (
    CONFIG,
    DEPLOY,
    DOCS,
    LOGS,
    NERVIOSO,
    SCRIPTS,
    SCRIPTS_PRO,
    TESTS,
    URA_ROOT,
)


class TestPaths:
    def test_ura_root_default(self):
        assert isinstance(URA_ROOT, Path)
        assert URA_ROOT.exists()

    def test_ura_root_from_env(self, monkeypatch):
        monkeypatch.setenv("URA_ROOT", "/tmp/test_ura")
        import importlib
        import shared.paths
        importlib.reload(shared.paths)
        assert shared.paths.URA_ROOT == Path("/tmp/test_ura")
        importlib.reload(shared.paths)

    def test_all_paths_are_path_objects(self):
        for p in [SCRIPTS, SCRIPTS_PRO, NERVIOSO, DEPLOY, TESTS, LOGS, CONFIG, DOCS]:
            assert isinstance(p, Path)

    def test_scripts_is_relative_to_root(self):
        assert SCRIPTS == URA_ROOT / "scripts"

    def test_scripts_pro_is_relative_to_root(self):
        assert SCRIPTS_PRO == URA_ROOT / "scripts/pro"

    def test_derived_paths_are_relative(self):
        assert DEPLOY == URA_ROOT / "deploy"
        assert DOCS == URA_ROOT / "docs"
        assert LOGS == URA_ROOT / "logs"
        assert CONFIG == URA_ROOT / "config"
        assert TESTS == URA_ROOT / "tests"
        assert NERVIOSO == URA_ROOT / ".nervioso"

    def test_ura_root_env_fallback(self, monkeypatch):
        monkeypatch.delenv("URA_ROOT", raising=False)
        import importlib
        import shared.paths
        importlib.reload(shared.paths)
        assert shared.paths.URA_ROOT == Path("/home/ramon/URA/ura_ia_1972")
        importlib.reload(shared.paths)
