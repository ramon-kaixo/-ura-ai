"""Tests for CodeAnalyzer (motor/brain/analyzer.py)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from motor.brain.analyzer import CodeAnalyzer


@pytest.fixture
def analyzer() -> CodeAnalyzer:
    return CodeAnalyzer()


class TestAnalyzeFile:
    def test_analyze_file_counts(self, analyzer: CodeAnalyzer) -> None:
        source = "def foo(): pass\nclass Bar: pass\n"
        with patch.object(Path, "read_text", return_value=source):
            result = analyzer.analyze_file(Path("test.py"))
            assert result["file"] == "test.py"
            assert result["functions"] == 1
            assert result["classes"] == 1
            assert result["lines"] == 2

    def test_analyze_file_syntax_error(self, analyzer: CodeAnalyzer) -> None:
        with patch.object(Path, "read_text", return_value="def foo(:"):
            result = analyzer.analyze_file(Path("bad.py"))
            assert result == {"error": "syntax_error"}

    def test_analyze_file_complex_functions(self, analyzer: CodeAnalyzer) -> None:
        lines = [f"    pass  # {i}" for i in range(55)]
        body = "\n".join(lines)
        source = f"def complex_fn():\n{body}\n"
        with patch.object(Path, "read_text", return_value=source):
            result = analyzer.analyze_file(Path("complex.py"))
            assert "complex_fn" in result["complex_functions"]


class TestAnalyzeModule:
    def test_analyze_module_rglob(self, analyzer: CodeAnalyzer) -> None:
        with patch.object(Path, "rglob") as mock_rglob:
            mock_rglob.return_value = [Path("a.py"), Path("b.py")]
            with patch.object(analyzer, "analyze_file") as mock_af:
                mock_af.return_value = {"file": "x", "functions": 1, "classes": 0, "lines": 10, "complex_functions": []}
                result = analyzer.analyze_module(Path("/mod"))
                assert len(result) == 2
                assert mock_af.call_count == 2
