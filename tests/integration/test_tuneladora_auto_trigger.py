"""Tests para scripts/pro/tuneladora/auto_trigger.py (AutoTrigger)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from scripts.pro.tuneladora.auto_trigger import AutoTrigger, TriggerCondition, TriggerEvent


@pytest.fixture
def trigger(tmp_path: Path) -> AutoTrigger:
    return AutoTrigger(nervioso=tmp_path / "nervioso")


class TestInit:
    def test_defaults(self, tmp_path: Path) -> None:
        t = AutoTrigger(nervioso=tmp_path / "n")
        assert t.strict is True
        assert t.mode == "gate"

    def test_properties(self, trigger: AutoTrigger) -> None:
        trigger.strict = False
        trigger.mode = "check"
        assert trigger.strict is False
        assert trigger.mode == "check"


class TestPipelineIntegration:
    def test_validate_with_pipeline_ok(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger._PIPELINE_AVAILABLE", True)
        from types import SimpleNamespace as _SN

        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger.Status", _SN(OK="OK", WARN="WARN", FAIL="FAIL"))
        runner = mock.Mock()
        runner.run.return_value = "OK"
        with mock.patch("scripts.pro.tuneladora.auto_trigger.PipelineRunner", return_value=runner):
            result = trigger.validate_with_pipeline([Path("a.py")])
        assert result["status"] == "ok"

    def test_validate_with_pipeline_warn(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger._PIPELINE_AVAILABLE", True)
        from types import SimpleNamespace as _SN

        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger.Status", _SN(OK="OK", WARN="WARN", FAIL="FAIL"))
        runner = mock.Mock()
        runner.run.return_value = "WARN"
        with mock.patch("scripts.pro.tuneladora.auto_trigger.PipelineRunner", return_value=runner):
            result = trigger.validate_with_pipeline([Path("a.py")])
        assert result["status"] == "warn"

    def test_validate_with_pipeline_fail(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger._PIPELINE_AVAILABLE", True)
        from types import SimpleNamespace as _SN

        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger.Status", _SN(OK="OK", WARN="WARN", FAIL="FAIL"))
        runner = mock.Mock()
        runner.run.return_value = "FAIL"
        with mock.patch("scripts.pro.tuneladora.auto_trigger.PipelineRunner", return_value=runner):
            result = trigger.validate_with_pipeline([Path("a.py")])
        assert result["status"] == "fail"

    def test_validate_sin_pipeline(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger._PIPELINE_AVAILABLE", False)
        result = trigger.validate_with_pipeline([Path("a.py")])
        assert result["status"] == "skip"
        assert "no disponible" in result["message"]

    def test_validate_sin_archivos(self, trigger: AutoTrigger) -> None:
        result = trigger.validate_with_pipeline([])
        assert result["status"] == "skip"

    def test_validate_pipeline_error(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger._PIPELINE_AVAILABLE", True)
        with mock.patch("scripts.pro.tuneladora.auto_trigger.Configuration"), mock.patch(
            "scripts.pro.tuneladora.auto_trigger.PipelineRunner",
            mock.Mock(side_effect=RuntimeError("boom")),
        ):
            result = trigger.validate_with_pipeline([Path("a.py")])
        assert result["status"] == "skip"
        assert "boom" in result["message"]

    def test_trigger_validation_sin_archivos(self, trigger: AutoTrigger) -> None:
        assert trigger.trigger_validation([])["status"] == "skip"

    def test_trigger_validation_delega(self, trigger: AutoTrigger) -> None:
        with mock.patch.object(trigger, "validate_with_pipeline", return_value={"status": "ok", "message": "m"}):
            result = trigger.trigger_validation([Path("a.py")])
        assert result["status"] == "ok"

    def test_validate_files_sin_pipeline(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger._PIPELINE_AVAILABLE", False)
        assert trigger.validate_files([Path("a.py")])["status"] == "skip"

    def test_validate_files_vacio(self, trigger: AutoTrigger) -> None:
        assert trigger.validate_files([])["status"] == "skip"


class TestShouldRun:
    def test_maintenance_con_cooldown(self, trigger: AutoTrigger) -> None:
        trigger.set_cooldown("maintenance", 3600)
        with mock.patch.object(trigger, "_check_ruff_errors", return_value=True):
            assert trigger.should_run_maintenance() is False

    def test_maintenance_sin_cooldown(self, trigger: AutoTrigger) -> None:
        with mock.patch.object(trigger, "_check_ruff_errors", return_value=True), mock.patch.object(
            trigger, "_check_git_dirty", return_value=False
        ):
            assert trigger.should_run_maintenance() is True

    def test_refinement_no_path(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        assert trigger.should_run_refinement(tmp_path / "no_existe.py") is False

    def test_refinement_cooldown(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("x\n" * 400)
        trigger.set_cooldown(f"refine:{f}", 3600)
        assert trigger.should_run_refinement(f) is False

    def test_healing(self, trigger: AutoTrigger) -> None:
        with mock.patch.object(trigger, "_check_recent_failures", return_value=True):
            assert trigger.should_run_healing("gate") is True

    def test_healing_cooldown(self, trigger: AutoTrigger) -> None:
        trigger.set_cooldown("heal:gate", 60)
        assert trigger.should_run_healing("gate") is False

    def test_intensive(self, trigger: AutoTrigger) -> None:
        with mock.patch.object(trigger, "_check_time_window", return_value=True):
            assert trigger.should_run_intensive() is True


class TestCooldown:
    def test_set_y_remaining(self, trigger: AutoTrigger) -> None:
        trigger.set_cooldown("x", 60)
        assert trigger._on_cooldown("x") is True
        assert trigger.cooldown_remaining("x") > 0

    def test_sin_cooldown(self, trigger: AutoTrigger) -> None:
        assert trigger._on_cooldown("x") is False
        assert trigger.cooldown_remaining("x") == 0.0

    def test_reset(self, trigger: AutoTrigger) -> None:
        trigger.set_cooldown("x", 60)
        trigger.reset_cooldown("x")
        assert trigger._on_cooldown("x") is False


class TestEvents:
    def test_record_y_get(self, trigger: AutoTrigger) -> None:
        trigger.record_event(TriggerEvent(condition="c", value=1, threshold=2, severity="info", message="m"))
        events = trigger.get_events()
        assert len(events) == 1
        assert events[0].condition == "c"

    def test_filtro_severidad(self, trigger: AutoTrigger) -> None:
        trigger.record_event(TriggerEvent(condition="a", value=1, threshold=2, severity="info"))
        trigger.record_event(TriggerEvent(condition="b", value=1, threshold=2, severity="critical"))
        assert len(trigger.get_events(severity="critical")) == 1

    def test_limit(self, trigger: AutoTrigger) -> None:
        for i in range(10):
            trigger.record_event(TriggerEvent(condition=f"c{i}", value=i, threshold=0))
        assert len(trigger.get_events(limit=3)) == 3

    def test_stats(self, trigger: AutoTrigger) -> None:
        trigger.set_cooldown("k", 100)
        stats = trigger.get_stats()
        assert stats["total_events"] == 0
        assert "k" in stats["active_cooldowns"]


class TestChecksInternos:
    def test_ruff_errors_detecta(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="Found 15 errors"),
        )
        assert trigger._check_ruff_errors() is True
        assert len(trigger._events) == 1

    def test_ruff_errores_pocos(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr="Found 3 errors"),
        )
        assert trigger._check_ruff_errors() is False

    def test_ruff_error_silencioso(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            mock.Mock(side_effect=OSError("no ruff")),
        )
        assert trigger._check_ruff_errors() is False

    def test_parse_ruff_count(self, trigger: AutoTrigger) -> None:
        assert trigger._parse_ruff_count("Found 42 errors") == 42
        assert trigger._parse_ruff_count("All checks passed") == 0

    def test_git_dirty(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout=" M a.py\n M b.py\n"),
        )
        assert trigger._check_git_dirty() is True

    def test_git_limpio(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout=""),
        )
        assert trigger._check_git_dirty() is False

    def test_file_needs_refinement_largo(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "largo.py"
        f.write_text("x\n" * 400)
        assert trigger._file_needs_refinement(f) is True

    def test_file_no_necesita(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "corto.py"
        f.write_text("def a():\n    pass\n")
        assert trigger._file_needs_refinement(f) is False

    def test_recent_failures_sin_log(self, trigger: AutoTrigger) -> None:
        assert trigger._check_recent_failures() is False

    def test_recent_failures_con_log(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        log_file = trigger._nervioso / "tuneladora_errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("ERROR x\nCRITICAL y\nERROR z\nERROR w\n")
        assert trigger._check_recent_failures() is True

    def test_time_window(self, trigger: AutoTrigger) -> None:
        now_hour = __import__("time").localtime().tm_hour
        assert trigger._check_time_window(0, 23) is True
        assert trigger._check_time_window(now_hour, now_hour) is True


class TestTriggerCondition:
    def test_dataclass(self) -> None:
        c = TriggerCondition(name="n", description="d", check_fn="f", threshold=10, cooldown=60)
        assert c.name == "n"
        assert c.cooldown == 60


class TestGaps:
    def test_validate_files_ok(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger._PIPELINE_AVAILABLE", True)
        from types import SimpleNamespace as _SN

        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger.Status", _SN(OK="OK", WARN="WARN", FAIL="FAIL"))
        runner = mock.Mock()
        runner.run.return_value = "OK"
        with mock.patch("scripts.pro.tuneladora.auto_trigger.PipelineRunner", return_value=runner):
            result = trigger.validate_files([Path("a.py")])
        assert result["status"] == "ok"

    def test_validate_files_fail(self, trigger: AutoTrigger, monkeypatch) -> None:
        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger._PIPELINE_AVAILABLE", True)
        from types import SimpleNamespace as _SN

        monkeypatch.setattr("scripts.pro.tuneladora.auto_trigger.Status", _SN(OK="OK", WARN="WARN", FAIL="FAIL"))
        runner = mock.Mock()
        runner.run.return_value = "FAIL"
        with mock.patch("scripts.pro.tuneladora.auto_trigger.PipelineRunner", return_value=runner):
            result = trigger.validate_files([Path("a.py")])
        assert result["status"] == "fail"

    def test_trigger_validation_fail_strict(self, trigger: AutoTrigger) -> None:
        trigger.strict = True
        with mock.patch.object(
            trigger, "validate_with_pipeline",
            return_value={"status": "fail", "message": "rechazado"},
        ):
            result = trigger.trigger_validation([Path("a.py")])
        assert result["status"] == "fail"

    def test_trigger_validation_fail_non_strict(self, trigger: AutoTrigger) -> None:
        trigger.strict = False
        with mock.patch.object(
            trigger, "validate_with_pipeline",
            return_value={"status": "fail", "message": "rechazado"},
        ):
            result = trigger.trigger_validation([Path("a.py")])
        assert result["status"] == "fail"

    def test_git_dirty_muchos_registra_evento(self, trigger: AutoTrigger, monkeypatch) -> None:
        out = "\n".join(f" M f{i}.py" for i in range(8))
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout=out),
        )
        assert trigger._check_git_dirty() is True
        assert len(trigger._events) == 1

    def test_file_needs_refinement_densidad_baja(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        f = tmp_path / "denso.py"
        f.write_text("a\n\n\n\n\nb\n\n\n\n\n")
        assert trigger._file_needs_refinement(f) is True

    def test_recent_failures_pocos(self, trigger: AutoTrigger, tmp_path: Path) -> None:
        log_file = trigger._nervioso / "tuneladora_errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("ERROR x\n")
        assert trigger._check_recent_failures() is False
