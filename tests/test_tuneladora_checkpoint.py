"""Tests para CheckpointManager (scripts/pro/tuneladora/checkpoint.py)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scripts.pro.tuneladora.checkpoint import CheckpointManager
from scripts.pro.tuneladora.ledger import ExecutionLedger


@pytest.fixture
def cp(tmp_path: Path) -> CheckpointManager:
    ledger = ExecutionLedger(tmp_path, "test")
    return CheckpointManager(tmp_path, "test", ledger._execution_id)


class TestCheckpoint:
    def test_is_done_returns_false_initially(self, cp):
        assert cp.is_done("pre") is False

    def test_mark_done_makes_is_done_true(self, cp):
        cp.mark_done("pre")
        assert cp.is_done("pre") is True

    def test_mark_done_multiple_phases(self, cp):
        cp.mark_done("pre")
        cp.mark_done("post")
        assert cp.is_done("pre") is True
        assert cp.is_done("post") is True

    def test_is_done_unknown_phase_is_false(self, cp):
        assert cp.is_done("nonexistent") is False

    def test_mark_skipped_does_not_mark_done(self, cp):
        cp.mark_skipped("test_phase")
        assert cp.is_done("test_phase") is False

    def test_last_completed_initially_empty(self, cp):
        assert cp.last_completed == ""

    def test_last_completed_after_mark(self, cp):
        cp.mark_done("pre")
        assert cp.last_completed == "pre"

    def test_last_completed_multiple(self, cp):
        cp.mark_done("pre")
        cp.mark_done("post")
        assert cp.last_completed == "post"

    def test_clear_resets_all(self, cp):
        cp.mark_done("pre")
        cp.mark_done("post")
        cp.clear()
        assert cp.is_done("pre") is False
        assert cp.is_done("post") is False
        assert cp.last_completed == ""


class TestPersistence:
    def test_resume_returns_false_initially(self, cp):
        assert cp.resume() is False

    def test_resume_after_mark(self, cp):
        cp.mark_done("pre")
        # Nuevo manager con mismo path y pipeline
        ledger = ExecutionLedger(cp._path.parent, "test")
        cp2 = CheckpointManager(cp._path.parent, "test", ledger._execution_id)
        assert cp2.resume() is True
        assert cp2.is_done("pre") is True

    def test_resume_same_execution_id_returns_false(self, cp):
        """Misma ejecucion no debe reanudar checkpoint previo."""
        cp.mark_done("pre")
        cp2 = CheckpointManager(cp._path.parent, "test", cp._execution_id)
        assert cp2.resume() is False

    def test_resume_different_pipeline_returns_false(self, tmp_path):
        ledger = ExecutionLedger(tmp_path, "pipeline_a")
        cp_a = CheckpointManager(tmp_path, "pipeline_a", ledger._execution_id)
        cp_a.mark_done("pre")

        ledger_b = ExecutionLedger(tmp_path, "pipeline_b")
        cp_b = CheckpointManager(tmp_path, "pipeline_b", ledger_b._execution_id)
        assert cp_b.resume() is False

    def test_save_creates_file(self, cp):
        cp.mark_done("pre")
        assert (cp._path).exists()
