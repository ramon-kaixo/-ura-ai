"""Tests for ProposalExecutor (motor/brain/executor.py)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from motor.brain.executor import ProposalExecutor


@pytest.fixture
def executor() -> ProposalExecutor:
    return ProposalExecutor()


class TestToTuneladoraTask:
    def test_refactor_task(self, executor: ProposalExecutor) -> None:
        task = executor.to_tuneladora_task({"type": "refactor", "target": "x.py", "priority": "high"})
        assert task["plugin"] == "code_quality"
        assert task["target"] == "x.py"

    def test_unknown_type_defaults(self, executor: ProposalExecutor) -> None:
        task = executor.to_tuneladora_task({"type": "unknown", "target": "y.py", "priority": "low"})
        assert task["plugin"] == "generic"


class TestProposalToArgs:
    def test_bool_flag(self, executor: ProposalExecutor) -> None:
        args = executor._proposal_to_args({"type": "refactor", "target": "x.py", "dry_run": True, "priority": "medium"})
        assert "--dry_run" in args

    def test_list_values(self, executor: ProposalExecutor) -> None:
        args = executor._proposal_to_args({"type": "test", "target": "mod.py", "paths": ["a", "b"], "priority": "high"})
        assert "--paths=a" in args
        assert "--paths=b" in args

    def test_none_skipped(self, executor: ProposalExecutor) -> None:
        args = executor._proposal_to_args({"type": "doc", "target": "mod.py", "optional": None, "priority": "low"})
        assert "--optional" not in " ".join(args)


class TestExecute:
    def test_execute_no_engine(self, executor: ProposalExecutor) -> None:
        with patch.object(executor, "_get_engine", return_value=None):
            result = executor.execute({"type": "test", "target": "mod.py", "priority": "low"})
            assert "error" in result

    def test_execute_success(self, executor: ProposalExecutor) -> None:
        mock_engine = MagicMock()
        mock_engine.run_script.return_value.returncode = 0
        with patch.object(executor, "_get_engine", return_value=mock_engine):
            result = executor.execute({"type": "refactor", "target": "mod.py", "priority": "medium"})
            assert result["status"] == "success"

    def test_execute_failure(self, executor: ProposalExecutor) -> None:
        mock_engine = MagicMock()
        mock_engine.run_script.return_value.returncode = 1
        with patch.object(executor, "_get_engine", return_value=mock_engine):
            result = executor.execute({"type": "refactor", "target": "mod.py", "priority": "medium"})
            assert result["status"] == "failed"
