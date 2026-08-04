"""Tests for PipelineRunner (scripts/pro/tuneladora/pipeline/runner.py)."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.pipeline.tools.base import Status
from scripts.pro.tuneladora.pipeline.runner import (
    PhaseResult,
    PipelineRunner,
    _api_diff,
    _build_json_report,
    _discover_focused_tests,
    _extract_api,
    _free_disk_gb,
)
from scripts.pro.tuneladora.pipeline.tools.base import Status


@pytest.fixture
def cfg() -> Configuration:
    return Configuration()


@pytest.fixture
def runner(cfg: Configuration) -> PipelineRunner:
    return PipelineRunner(cfg, mode="check")


class TestPipelineRunnerInit:
    def test_init_defaults(self, runner: PipelineRunner):
        assert runner.mode == "check"
        assert runner.files == []

    def test_init_with_files(self, cfg: Configuration):
        r = PipelineRunner(cfg, mode="fix", files=["a.py", "b.py"])
        assert r.mode == "fix"
        assert r.files == ["a.py", "b.py"]

    def test_snapshot_manager_set(self, runner: PipelineRunner):
        assert runner.snapshot_manager is not None


class TestPipelineRunnerPhases:
    def test_phase_static(self, runner: PipelineRunner):
        results = runner.phase_static()
        assert isinstance(results, list)

    def test_phase_dynamic(self, runner: PipelineRunner):
        with mock.patch.object(runner.tools["pytest"], "run_check", return_value=mock.Mock(status=Status.OK, seconds=1.0, summary="1 passed")):
            results = runner.phase_dynamic()
            assert isinstance(results, list)

    def test_phase_integrity(self, runner: PipelineRunner):
        results = runner.phase_integrity()
        for r in results:
            assert isinstance(r.name, str)
            assert isinstance(r.status, Status)


class TestPipelineRunnerRun:
    @pytest.mark.slow
    def test_run_returns_status(self, runner: PipelineRunner):
        with mock.patch.multiple(
            runner,
            phase_snapshot=mock.DEFAULT,
            phase_static=mock.DEFAULT,
            phase_dynamic=mock.DEFAULT,
            phase_index=mock.DEFAULT,
            phase_integrity=mock.DEFAULT,
            phase_verdict=mock.DEFAULT,
            _acquire_lock=mock.DEFAULT,
            _finish=mock.DEFAULT,
        ):
            runner._acquire_lock.return_value = True
            runner._finish.return_value = Status.OK
            runner.phase_snapshot.return_value = [mock.Mock(name="snap", status=Status.OK)]
            runner.phase_static.return_value = [mock.Mock(name="static", status=Status.OK)]
            runner.phase_dynamic.return_value = [mock.Mock(name="dynamic", status=Status.OK)]
            runner.phase_index.return_value = [mock.Mock(name="index", status=Status.OK)]
            runner.phase_integrity.return_value = [mock.Mock(name="integrity", status=Status.OK)]
            runner.phase_verdict.return_value = (Status.OK, "all good")
            result = runner.run()
            assert result == Status.OK


class TestFreeDiskGB:
    def test_returns_float_or_none(self):
        gb = _free_disk_gb(Path("/tmp"))
        assert gb is None or isinstance(gb, (int, float))

    def test_none_on_bad_path(self):
        gb = _free_disk_gb(Path("/nonexistent_path_xyz"))
        assert gb is None


class TestJsonReport:
    def test_build_report_dict(self):
        report = _build_json_report(
            episode_id="ep-1", verdict=Status.OK, msg="todo bien",
            duration_ms=1234.5, mode="check", files=["a.py", "b.py"],
            telemetry={"n_files": 2}, sofia_n_criticos=0, sofia_n_advertencias=1,
        )
        assert report["episode_id"] == "ep-1"
        assert report["verdict"] == "OK"
        assert report["pipeline"] == "tuneladora"
        assert report["mode"] == "check"
        assert report["files"] == ["a.py", "b.py"]
        assert report["sofia"] == {"criticos": 0, "advertencias": 1}
        assert report["duration_ms"] == 1234.5
        assert report["telemetry"]["n_files"] == 2

    def test_build_report_fail_verdict(self):
        report = _build_json_report(
            episode_id="ep-2", verdict=Status.FAIL, msg="fallo",
            duration_ms=10.0, mode="gate", files=[], telemetry={},
            sofia_n_criticos=2, sofia_n_advertencias=0,
        )
        assert report["verdict"] == "FAIL"
        assert report["summary"] == "fallo"

    def test_write_json_report(self, runner: PipelineRunner, tmp_path):
        runner.cfg.ura_root = tmp_path
        runner._write_json_report("ep-3", Status.OK, "ok", 99.0)
        out = tmp_path / "data" / "tuneladora_reports" / "ep-3.json"
        assert out.exists()
        import json as _json

        data = _json.loads(out.read_text())
        assert data["episode_id"] == "ep-3"
        assert data["verdict"] == "OK"

    def test_write_json_report_error_silencioso(self, runner: PipelineRunner, tmp_path):
        runner.cfg.ura_root = tmp_path / "no" / "existe"
        (tmp_path / "no").write_text("soy un archivo")
        runner._write_json_report("ep-4", Status.OK, "ok", 1.0)  # no debe lanzar


class TestFuncionesPuras:
    def test_discover_focused_tests(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_modulo.py").write_text("")
        (tmp_path / "tests" / "test_modulo_extra.py").write_text("")
        focused = _discover_focused_tests(["motor/x/modulo.py", "notas.txt", "motor/y/modulo.py"])
        assert "tests/test_modulo.py" in focused
        assert focused.count("tests/test_modulo.py") == 1

    def test_extract_api(self) -> None:
        import ast

        tree = ast.parse("def foo(a, b):\n    return 1\n\nclass Bar:\n    pass\n\nasync def baz():\n    pass\n")
        api = _extract_api(tree)
        assert "def foo" in api
        assert api["def foo"]["args"] == "a, b"
        assert "class Bar" in api
        assert "async def baz" in api

    def test_api_diff(self) -> None:
        old = {"def a": {"args": "x", "returns": "None"}, "def b": {"args": "", "returns": "None"}}
        new = {"def a": {"args": "x, y", "returns": "None"}, "def c": {"args": "", "returns": "None"}}
        changes = _api_diff(old, new)
        text = "\n".join(changes)
        assert "ELIMINADO" in text and "def b" in text
        assert "NUEVO" in text and "def c" in text
        assert "def a" in text


class TestPhaseVerdict:
    def _pr(self, name: str, status: Status) -> PhaseResult:
        return PhaseResult(name, status)

    def test_fail_prioridad(self) -> None:
        runner = PipelineRunner(Configuration(), mode="check")
        results = [
            [self._pr("static", Status.OK), self._pr("static", Status.WARN)],
            [self._pr("dynamic", Status.FAIL)],
        ]
        verdict, msg = runner.phase_verdict(results)
        assert verdict == Status.FAIL
        assert "FAILED" in msg

    def test_warn(self) -> None:
        runner = PipelineRunner(Configuration(), mode="check")
        results = [[self._pr("static", Status.WARN)], [self._pr("d", Status.OK)]]
        verdict, msg = runner.phase_verdict(results)
        assert verdict == Status.WARN
        assert "1 warnings" in msg

    def test_ok(self) -> None:
        runner = PipelineRunner(Configuration(), mode="check")
        results = [[self._pr("static", Status.OK)], [self._pr("d", Status.OK)]]
        verdict, msg = runner.phase_verdict(results)
        assert verdict == Status.OK
        assert "passed all" in msg


class TestBuildJsonReportExtra:
    def test_fail_verdict(self) -> None:
        report = _build_json_report(
            episode_id="e", verdict=Status.FAIL, msg="boom",
            duration_ms=1.0, mode="gate", files=["a.py"],
            telemetry={}, sofia_n_criticos=2, sofia_n_advertencias=0,
        )
        assert report["verdict"] == "FAIL"
        assert report["sofia"]["criticos"] == 2
