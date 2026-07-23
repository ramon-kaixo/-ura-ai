"""Tests para ExecutionLedger (scripts/pro/tuneladora/ledger.py)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from scripts.pro.tuneladora.ledger import ExecutionLedger


@pytest.fixture
def ledger() -> ExecutionLedger:
    tmp = Path(tempfile.mkdtemp())
    return ExecutionLedger(tmp, "test_pipeline")


class TestRecord:
    def test_creates_entry_on_init(self, ledger):
        entry = ledger._entry
        assert entry["pipeline"] == "test_pipeline"
        assert entry["trigger"] == "manual"
        assert entry["execution_id"] != ""

    def test_set_trigger(self, ledger):
        ledger.set_trigger("cron")
        assert ledger._entry["trigger"] == "cron"

    def test_phase_start(self, ledger):
        ledger.phase_start("pre")
        assert "pre" in ledger._entry["phases_executed"]

    def test_phase_skip(self, ledger):
        ledger.phase_skip("post")
        assert "post" in ledger._entry["phases_skipped"]

    def test_plugin_done(self, ledger):
        ledger.plugin_done("ruff", 1.5, "ok")
        assert "ruff" in ledger._entry["plugins_activated"]
        assert ledger._entry["plugin_durations"]["ruff"] == 1.5

    def test_plugin_done_default_status(self, ledger):
        ledger.plugin_done("fmt", 0.5)
        assert ledger._entry["plugin_status"]["fmt"] == "ok"

    def test_add_warning(self, ledger):
        ledger.add_warning("cpu alta")
        assert "cpu alta" in ledger._entry["warnings"]

    def test_add_error(self, ledger):
        ledger.add_error("disk full")
        assert "disk full" in ledger._entry["errors"]

    def test_set_promotion(self, ledger):
        ledger.set_promotion(True)
        assert ledger._entry["promotion"] is True

    def test_set_rollback(self, ledger):
        ledger.set_rollback(True)
        assert ledger._entry["rollback"] is True

    def test_set_changes(self, ledger):
        ledger.set_changes(10, 500)
        assert ledger._entry["changed_files"] == 10
        assert ledger._entry["changed_lines"] == 500

    def test_set_result(self, ledger):
        ledger.set_result("success")
        assert ledger._entry["result"] == "success"

    def test_goal_decision_plan_evaluation(self, ledger):
        ledger.set_goal({"goal": "clean"})
        assert ledger._entry["goal"] == {"goal": "clean"}
        ledger.add_decision("skip", {"reason": "noop"})
        assert len(ledger._entry["decisions"]) == 1
        ledger.set_plan({"steps": []})
        assert ledger._entry["plan"] == {"steps": []}
        ledger.set_evaluation(0.8, "approve", {"quality": "ok"})
        assert ledger._entry["evaluation"]["score"] == 0.8


class TestPersistence:
    def test_save_creates_json(self, ledger):
        path = ledger.save()
        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert data["pipeline"] == "test_pipeline"
        assert data["execution_id"] == ledger._execution_id

    def test_save_includes_timing(self, ledger):
        import time

        time.sleep(0.01)
        path = ledger.save()
        with open(path) as f:
            data = json.load(f)
        assert data["duration_ms"] > 0
        assert data["end_time"] != ""

    def test_save_directory_created(self, ledger):
        path = ledger.save()
        assert path.parent.exists()

    def test_multiple_saves_different_files(self, ledger):
        p1 = ledger.save()
        p2 = ExecutionLedger(ledger._nervioso, "test_pipeline").save()
        assert p1.name != p2.name

    def test_save_entry_is_serializable(self, ledger):
        ledger.set_goal({"nested": {"key": "value"}})
        ledger.add_decision("type1", {"data": [1, 2, 3]})
        path = ledger.save()
        with open(path) as f:
            data = json.load(f)
        assert data["goal"]["nested"]["key"] == "value"

    def test_resource_sample_does_not_crash(self, ledger):
        ledger.resource_sample()
        assert True  # No exception

    def test_git_commit_does_not_crash(self, ledger):
        ledger.set_git_commit()
        assert True  # No exception (subprocess puede fallar pero no crashea)
