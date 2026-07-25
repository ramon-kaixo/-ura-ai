"""Tests for AutoTrigger (scripts/pro/tuneladora/auto_trigger.py)."""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.pro.tuneladora.auto_trigger import AutoTrigger, TriggerEvent


@pytest.fixture
def trigger(tmp_path: Path) -> AutoTrigger:
    return AutoTrigger(nervioso=tmp_path)


class TestShouldRun:
    def test_should_run_maintenance_false_when_clean(self, trigger: AutoTrigger) -> None:
        with (
            patch.object(trigger, "_check_ruff_errors", return_value=False),
            patch.object(trigger, "_check_git_dirty", return_value=False),
        ):
            assert not trigger.should_run_maintenance()

    def test_should_run_maintenance_true_with_ruff(self, trigger: AutoTrigger) -> None:
        with (
            patch.object(trigger, "_check_ruff_errors", return_value=True),
            patch.object(trigger, "_check_git_dirty", return_value=False),
        ):
            assert trigger.should_run_maintenance()

    def test_should_run_refinement_small_file(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "small.py"
        f.write_text("x = 1\n")
        assert not trigger.should_run_refinement(f)

    def test_should_run_healing_default_false(self, trigger: AutoTrigger) -> None:
        assert not trigger.should_run_healing()

    def test_should_run_intensive_outside_window(self, trigger: AutoTrigger) -> None:
        with patch("scripts.pro.tuneladora.auto_trigger.time.localtime") as mock:
            mock.return_value = time.struct_time((2026, 1, 1, 10, 0, 0, 0, 0, 0))
            assert not trigger.should_run_intensive()


class TestCooldown:
    def test_cooldown_active(self, trigger: AutoTrigger) -> None:
        trigger.set_cooldown("test", 3600)
        assert trigger._on_cooldown("test")

    def test_cooldown_expired(self, trigger: AutoTrigger) -> None:
        trigger._last_trigger["test"] = time.time() - 7200
        trigger._cooldown["test"] = 3600
        assert not trigger._on_cooldown("test")

    def test_cooldown_remaining(self, trigger: AutoTrigger) -> None:
        trigger.set_cooldown("x", 100)
        remaining = trigger.cooldown_remaining("x")
        assert 0 < remaining <= 100

    def test_cooldown_reset(self, trigger: AutoTrigger) -> None:
        trigger.set_cooldown("x", 100)
        trigger.reset_cooldown("x")
        assert trigger.cooldown_remaining("x") == 0.0


class TestEvents:
    def test_record_event(self, trigger: AutoTrigger) -> None:
        trigger.record_event(TriggerEvent("test", 42, None))
        assert len(trigger.get_events()) == 1

    def test_get_events_limit(self, trigger: AutoTrigger) -> None:
        for i in range(10):
            trigger.record_event(TriggerEvent("t", i, None))
        assert len(trigger.get_events(limit=3)) == 3

    def test_get_events_severity(self, trigger: AutoTrigger) -> None:
        trigger.record_event(TriggerEvent("t1", 1, None, severity="info"))
        trigger.record_event(TriggerEvent("t2", 2, None, severity="warning"))
        assert len(trigger.get_events(severity="warning")) == 1

    def test_get_stats_structure(self, trigger: AutoTrigger) -> None:
        trigger.set_cooldown("p1", 100)
        stats = trigger.get_stats()
        assert "total_events" in stats
        assert "last_trigger" in stats
        assert "active_cooldowns" in stats


class TestInternal:
    def test_parse_ruff_count(self, trigger: AutoTrigger) -> None:
        assert trigger._parse_ruff_count("Found 5 errors") == 5
        assert trigger._parse_ruff_count("All good!") == 0

    def test_file_needs_refinement_long(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "long.txt"
        f.write_text("\n".join(f"line {i}" for i in range(400)))
        assert trigger._file_needs_refinement(f)

    def test_file_needs_refinement_dense(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "dense.txt"
        f.write_text("\n".join([f"content {i}" for i in range(10)] + [""] * 50))
        assert trigger._file_needs_refinement(f)

    def test_file_needs_refinement_ok(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "ok.txt"
        f.write_text("\n".join(f"line {i}" for i in range(20)))
        assert not trigger._file_needs_refinement(f)


# ── Pipeline integration tests ─────────────────────────────────────────────


class TestValidateWithPipeline:
    def test_ok(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("scripts.pro.tuneladora.auto_trigger.PipelineRunner") as m_runner, \
             patch("scripts.pro.tuneladora.auto_trigger.Configuration"):
            from scripts.pro.tuneladora.pipeline.tools.base import Status
            inst = m_runner.return_value
            inst.run.return_value = Status.OK
            result = trigger.validate_with_pipeline([f])
            assert result["status"] == "ok"

    def test_warn(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("scripts.pro.tuneladora.auto_trigger.PipelineRunner") as m_runner, \
             patch("scripts.pro.tuneladora.auto_trigger.Configuration"):
            from scripts.pro.tuneladora.pipeline.tools.base import Status
            inst = m_runner.return_value
            inst.run.return_value = Status.WARN
            result = trigger.validate_with_pipeline([f])
            assert result["status"] == "warn"

    def test_fail(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("scripts.pro.tuneladora.auto_trigger.PipelineRunner") as m_runner, \
             patch("scripts.pro.tuneladora.auto_trigger.Configuration"):
            from scripts.pro.tuneladora.pipeline.tools.base import Status
            inst = m_runner.return_value
            inst.run.return_value = Status.FAIL
            result = trigger.validate_with_pipeline([f])
            assert result["status"] == "fail"

    def test_skip_on_empty_files(self, trigger: AutoTrigger) -> None:
        result = trigger.validate_with_pipeline([])
        assert result["status"] == "skip"

    def test_graceful_degradation(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("scripts.pro.tuneladora.auto_trigger._PIPELINE_AVAILABLE", False):
            result = trigger.validate_with_pipeline([f])
            assert result["status"] == "skip"
            assert "Pipeline no disponible" in result["message"]


class TestTriggerValidation:
    def test_strict_blocks_on_fail(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        trigger.strict = True
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch.object(trigger, "validate_with_pipeline", return_value={"status": "fail", "message": "nope"}):
            result = trigger.trigger_validation([f])
            assert result["status"] == "fail"

    def test_non_strict_continues_on_fail(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        trigger.strict = False
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch.object(trigger, "validate_with_pipeline", return_value={"status": "fail", "message": "nope"}):
            result = trigger.trigger_validation([f])
            assert result["status"] == "fail"

    def test_ok_passes_through(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch.object(trigger, "validate_with_pipeline", return_value={"status": "ok", "message": "good"}):
            result = trigger.trigger_validation([f])
            assert result["status"] == "ok"

    def test_warn_passes_through(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch.object(trigger, "validate_with_pipeline", return_value={"status": "warn", "message": "warn"}):
            result = trigger.trigger_validation([f])
            assert result["status"] == "warn"

    def test_skip_passes_through(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch.object(trigger, "validate_with_pipeline", return_value={"status": "skip", "message": "skip"}):
            result = trigger.trigger_validation([f])
            assert result["status"] == "skip"

    def test_empty_files(self, trigger: AutoTrigger) -> None:
        result = trigger.trigger_validation([])
        assert result["status"] == "skip"


class TestAutoTriggerConstructor:
    def test_default_mode(self) -> None:
        t = AutoTrigger()
        assert t.mode == "gate"
        assert t.strict is True

    def test_custom_mode(self) -> None:
        t = AutoTrigger(mode="check", strict=False)
        assert t.mode == "check"
        assert t.strict is False

    def test_mode_setter(self, trigger: AutoTrigger) -> None:
        trigger.mode = "fix"
        assert trigger.mode == "fix"

    def test_strict_setter(self, trigger: AutoTrigger) -> None:
        trigger.strict = False
        assert trigger.strict is False
