"""Tests for core/change_guardian.py."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.change_guardian import (
    _get_modified_tracked_files,
    _load_patterns,
    _save_pattern,
    get_failure_patterns,
    get_failure_summary,
)


class TestGetModifiedTrackedFiles:
    @patch("core.change_guardian._git")
    def test_returns_files(self, mock_git):
        mock_git.return_value = (True, "file1.py\nfile2.py\n")
        result = _get_modified_tracked_files()
        assert result == ["file1.py", "file2.py"]

    @patch("core.change_guardian._git")
    def test_empty_output(self, mock_git):
        mock_git.return_value = (True, "")
        result = _get_modified_tracked_files()
        assert result == []

    @patch("core.change_guardian._git")
    def test_ignores_whitespace(self, mock_git):
        mock_git.return_value = (True, "  \n  \n")
        result = _get_modified_tracked_files()
        assert result == []


class TestLoadPatterns:
    def test_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.change_guardian.PATTERNS_FILE", tmp_path / "no_existe.json")
        assert _load_patterns() == []

    def test_valid_json(self, tmp_path, monkeypatch):
        f = tmp_path / "patterns.json"
        f.write_text('[{"tipo": "test"}]')
        monkeypatch.setattr("core.change_guardian.PATTERNS_FILE", f)
        result = _load_patterns()
        assert result == [{"tipo": "test"}]

    def test_invalid_json(self, tmp_path, monkeypatch):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        monkeypatch.setattr("core.change_guardian.PATTERNS_FILE", f)
        assert _load_patterns() == []


class TestSavePattern:
    def test_creates_file(self, tmp_path, monkeypatch):
        f = tmp_path / "patterns.json"
        monkeypatch.setattr("core.change_guardian.PATTERNS_FILE", f)
        _save_pattern("test", ["a.py"], "error", "diff")
        assert f.exists()
        data = json.loads(f.read_text())
        assert len(data) == 1
        assert data[0]["tipo_cambio"] == "test"
        assert data[0]["archivos"] == ["a.py"]

    def test_appends(self, tmp_path, monkeypatch):
        f = tmp_path / "patterns.json"
        f.write_text('[{"tipo_cambio": "old"}]')
        monkeypatch.setattr("core.change_guardian.PATTERNS_FILE", f)
        _save_pattern("new", ["b.py"], "err", "diff")
        data = json.loads(f.read_text())
        assert len(data) == 2
        assert data[1]["tipo_cambio"] == "new"


class TestGetFailurePatterns:
    def test_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.change_guardian.PATTERNS_FILE", tmp_path / "no.json")
        assert get_failure_patterns() == []

    def test_with_data(self, tmp_path, monkeypatch):
        f = tmp_path / "patterns.json"
        f.write_text('[{"tipo_cambio": "x"}]')
        monkeypatch.setattr("core.change_guardian.PATTERNS_FILE", f)
        result = get_failure_patterns()
        assert len(result) == 1


class TestGetFailureSummary:
    def test_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.change_guardian.PATTERNS_FILE", tmp_path / "no.json")
        assert get_failure_summary() == "Sin fallos registrados"

    def test_with_patterns(self, tmp_path, monkeypatch):
        f = tmp_path / "patterns.json"
        f.write_text(json.dumps([
            {"fecha": "2024-01-01T00:00:00", "tipo_cambio": "bug", "error": "something failed"}
        ]))
        monkeypatch.setattr("core.change_guardian.PATTERNS_FILE", f)
        result = get_failure_summary()
        assert "bug" in result
        assert "something failed" in result
