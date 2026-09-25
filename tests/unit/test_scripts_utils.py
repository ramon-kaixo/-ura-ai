import pytest
"""Tests for scripts/pro/utils.py."""
from scripts.pro.utils import log, scan_project


class TestUtils:
    @pytest.mark.unit
    def test_log(self):
        log("msg")
    @pytest.mark.unit
    def test_scan_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.pro.utils.URA_ROOT", tmp_path)
        assert scan_project() == []
    @pytest.mark.unit
    def test_scan_excludes(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir(parents=True)
        (tmp_path / ".git" / "a.py").write_text("x")
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "b.py").write_text("x")
        monkeypatch.setattr("scripts.pro.utils.URA_ROOT", tmp_path)
        r = scan_project()
        assert len(r) == 1 and r[0].name == "b.py"
