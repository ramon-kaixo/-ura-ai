"""Tests para core/path_setup.py."""

import sys
from pathlib import Path

import core.path_setup as ps


class TestSetupPath:
    def test_setup_path_anade_a_sys_path(self) -> None:
        original_len = len(sys.path)
        ps.setup_path()
        assert len(sys.path) >= original_len
        assert any(Path(__file__).resolve().parents[2].name in p for p in sys.path)

    def test_setup_path_idempotente(self) -> None:
        ps.setup_path()
        count_before = sys.path.count(str(ps.get_project_root()))
        ps.setup_path()
        count_after = sys.path.count(str(ps.get_project_root()))
        assert count_after == count_before


class TestGetProjectRoot:
    def test_devuelve_path(self) -> None:
        ps._PROJECT_ROOT = None
        root = ps.get_project_root()
        assert isinstance(root, Path)
        assert root.exists()

    def test_no_reinicializa_si_ya_setup(self) -> None:
        ps.setup_path()
        root1 = ps.get_project_root()
        root2 = ps.get_project_root()
        assert root1 is root2


class TestModuleState:
    def test_project_root_inicialmente_none(self) -> None:
        # Solo verificamos que el módulo tiene la variable
        assert hasattr(ps, "_PROJECT_ROOT")
