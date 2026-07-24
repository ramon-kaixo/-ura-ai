"""Tests for ArchitectureAdvisor (motor/brain/advisor.py)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from motor.brain.advisor import ArchitectureAdvisor


@pytest.fixture
def advisor() -> ArchitectureAdvisor:
    return ArchitectureAdvisor()


class TestPropose:
    def test_propose_returns_list(self, advisor: ArchitectureAdvisor) -> None:
        with patch.object(advisor.analyzer, "analyze_module") as mock_analyze:
            mock_analyze.return_value = [
                {"file": "mod.py", "complex_functions": ["foo"], "lines": 100}
            ]
            result = advisor.propose("/fake/path")
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["type"] == "refactor"

    def test_propose_split_large_file(self, advisor: ArchitectureAdvisor) -> None:
        with patch.object(advisor.analyzer, "analyze_module") as mock_analyze:
            mock_analyze.return_value = [
                {"file": "big.py", "complex_functions": [], "lines": 600}
            ]
            result = advisor.propose("/fake/path")
            assert len(result) == 1
            assert result[0]["type"] == "split"
            assert result[0]["priority"] == "medium"

    def test_propose_empty_when_clean(self, advisor: ArchitectureAdvisor) -> None:
        with patch.object(advisor.analyzer, "analyze_module") as mock_analyze:
            mock_analyze.return_value = [
                {"file": "clean.py", "complex_functions": [], "lines": 50}
            ]
            result = advisor.propose("/fake/path")
            assert result == []

    def test_propose_calls_analyze_module(self, advisor: ArchitectureAdvisor) -> None:
        with patch.object(advisor.analyzer, "analyze_module") as mock_analyze:
            mock_analyze.return_value = []
            advisor.propose("/some/path")
            mock_analyze.assert_called_once_with(Path("/some/path"))
