"""Tests for PipelineRunner (scripts/pro/tuneladora/pipeline/runner.py)."""
from __future__ import annotations

import time
from pathlib import Path
from unittest import mock

import pytest

from scripts.pro.tuneladora.config import Configuration
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


class TestPhasesConMocks:
    def _runner(self, cfg: Configuration) -> PipelineRunner:
        return PipelineRunner(cfg, mode="check", files=["motor/x/modulo.py"])

    def test_phase_dynamic_skip_sin_pytest(self, cfg: Configuration) -> None:
        runner = self._runner(cfg)
        runner.tools["pytest"] = mock.Mock()
        runner.tools["pytest"].is_available.return_value = False
        results = runner.phase_dynamic()
        assert results[0].status == Status.SKIP

    def test_phase_dynamic_focused_ok(self, cfg: Configuration, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_modulo.py").write_text("")
        runner = self._runner(cfg)
        tool = mock.Mock()
        tool.is_available.return_value = True
        tool.run_check.return_value = mock.Mock(status=Status.OK, detail="")
        runner.tools["pytest"] = tool
        runner.cache = mock.Mock()
        runner.cache.get.return_value = None
        results = runner.phase_dynamic()
        assert results[0].name == "pytest_focused"
        assert results[0].status == Status.OK
        runner.cache.set.assert_called_once()

    def test_phase_dynamic_focused_fail_encola(self, cfg: Configuration, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_modulo.py").write_text("")
        runner = self._runner(cfg)
        tool = mock.Mock()
        tool.is_available.return_value = True
        tool.run_check.return_value = mock.Mock(status=Status.FAIL, detail="boom")
        runner.tools["pytest"] = tool
        runner.cache = mock.Mock()
        runner.cache.get.return_value = None
        runner.llm_fallback = mock.Mock()
        runner.llm_fallback.analyze.return_value = "sug"
        runner.pending_queue = mock.Mock()
        results = runner.phase_dynamic()
        assert results[0].status == Status.FAIL
        runner.pending_queue.add.assert_called_once()
        assert runner.llm_fallback.analyze.call_count == 1

    def test_phase_dynamic_cache_hit(self, cfg: Configuration, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_modulo.py").write_text("")
        runner = self._runner(cfg)
        tool = mock.Mock()
        tool.is_available.return_value = True
        runner.tools["pytest"] = tool
        runner.cache = mock.Mock()
        runner.cache.get.return_value = mock.Mock(status=Status.OK)
        results = runner.phase_dynamic()
        assert results[0].name == "pytest_focused"
        assert results[0].status == Status.OK
        tool.run_check.assert_not_called()

    def test_phase_dynamic_full_fail(self, cfg: Configuration) -> None:
        runner = PipelineRunner(cfg, mode="check", files=[])
        tool = mock.Mock()
        tool.is_available.return_value = True
        tool.run_check.return_value = mock.Mock(status=Status.FAIL, detail="err")
        runner.tools["pytest"] = tool
        runner.llm_fallback = mock.Mock()
        runner.llm_fallback.analyze.return_value = None
        runner.pending_queue = mock.Mock()
        results = runner.phase_dynamic()
        assert results[0].name == "pytest_full"
        assert results[0].status == Status.FAIL
        runner.pending_queue.add.assert_called_once()

    def test_phase_dynamic_full_ok(self, cfg: Configuration) -> None:
        runner = PipelineRunner(cfg, mode="check", files=[])
        tool = mock.Mock()
        tool.is_available.return_value = True
        tool.run_check.return_value = mock.Mock(status=Status.OK, detail="")
        runner.tools["pytest"] = tool
        runner.llm_fallback = mock.Mock()
        runner.pending_queue = mock.Mock()
        results = runner.phase_dynamic()
        assert results[0].name == "pytest_full"
        assert results[0].status == Status.OK
        runner.pending_queue.add.assert_not_called()

    def test_phase_static_tools(self, cfg: Configuration) -> None:
        runner = PipelineRunner(cfg, mode="check", files=["motor/x/modulo.py"])
        runner._run_py_compile = mock.Mock()
        runner._run_py_compile.return_value = mock.Mock(status=Status.OK)
        runner._run_tool_with_retry = mock.Mock()
        runner._run_tool_with_retry.return_value = mock.Mock(status=Status.OK, detail="")
        for name in ("ruff", "mypy", "bandit"):
            tool = mock.Mock()
            tool.is_available.return_value = True
            runner.tools[name] = tool
        results = runner.phase_static()
        names = {r.name for r in results}
        assert {"ruff", "mypy", "bandit"} <= names

    def test_phase_static_skip(self, cfg: Configuration) -> None:
        runner = PipelineRunner(cfg, mode="check", files=["motor/x/modulo.py"])
        runner._run_py_compile = mock.Mock()
        runner._run_py_compile.return_value = mock.Mock(status=Status.OK)
        for name in ("ruff", "mypy", "bandit"):
            tool = mock.Mock()
            tool.is_available.return_value = False
            runner.tools[name] = tool
        results = runner.phase_static()
        assert any(r.name == "ruff" and r.status == Status.SKIP for r in results)
        assert any(r.name == "bandit" and r.status == Status.SKIP for r in results)


class TestLockPidMuerto:
    def test_lock_pid_muerto_se_sobrescribe(self, cfg: Configuration, tmp_path, monkeypatch) -> None:
        from scripts.pro.tuneladora.pipeline.runner import _pid_alive

        runner = PipelineRunner(cfg, mode="check", files=[])
        runner.cfg.tuneladora_dir = tmp_path
        runner.cfg.tuneladora_dir.mkdir(parents=True, exist_ok=True)
        lock_path = tmp_path / "pipeline.lock"
        import json as _json

        lock_path.write_text(_json.dumps({"pid": 999999999, "start": time.time(), "mode": "check"}))
        with mock.patch("scripts.pro.tuneladora.pipeline.runner._pid_alive", return_value=False):
            ok = runner._acquire_lock()
        assert ok is True
        assert runner._lock_acquired is True

    def test_lock_pid_vivo_bloquea(self, cfg: Configuration, tmp_path, monkeypatch) -> None:
        runner = PipelineRunner(cfg, mode="check", files=[])
        runner.cfg.tuneladora_dir = tmp_path
        runner.cfg.tuneladora_dir.mkdir(parents=True, exist_ok=True)
        lock_path = tmp_path / "pipeline.lock"
        import json as _json

        lock_path.write_text(_json.dumps({"pid": 999999999, "start": time.time(), "mode": "check"}))
        with mock.patch("scripts.pro.tuneladora.pipeline.runner._pid_alive", return_value=True):
            ok = runner._acquire_lock()
        assert ok is False

    def test_pid_alive_helpers(self) -> None:
        from scripts.pro.tuneladora.pipeline.runner import _pid_alive

        assert _pid_alive(0) is False
        assert _pid_alive(-5) is False
        assert _pid_alive(999999999) is False
        import os

        assert _pid_alive(os.getpid()) is True


class TestCoverageReporte:
    def test_reporte_incluye_coverage(self) -> None:
        report = _build_json_report(
            episode_id="e", verdict=Status.OK, msg="ok", duration_ms=1.0,
            mode="check", files=["a.py"],
            telemetry={"coverage_global": 78.5, "tests_failed": 2},
            sofia_n_criticos=0, sofia_n_advertencias=0,
        )
        assert report["coverage"]["global"] == 78.5
        assert report["coverage"]["tests_failed"] == 2
        assert report["coverage"]["tests_total"] == 0  # default

    def test_reporte_coverage_default_cero(self) -> None:
        report = _build_json_report(
            episode_id="e", verdict=Status.OK, msg="ok", duration_ms=1.0,
            mode="check", files=[], telemetry={},
            sofia_n_criticos=0, sofia_n_advertencias=0,
        )
        assert report["coverage"]["global"] == 0

    def test_recolectar_coverage_xml(self, cfg: Configuration, tmp_path: Path) -> None:
        runner = PipelineRunner(cfg, mode="check", files=[])
        runner.cfg.ura_root = tmp_path
        (tmp_path / "coverage.xml").write_text(
            '<?xml version="1.0"?><coverage line-rate="0.785"><packages/></coverage>'
        )
        runner._recolectar_coverage()
        assert runner._telemetry["coverage_global"] == 78.5

    def test_recolectar_sin_xml(self, cfg: Configuration, tmp_path: Path) -> None:
        runner = PipelineRunner(cfg, mode="check", files=[])
        runner.cfg.ura_root = tmp_path
        runner._recolectar_coverage()
        assert "coverage_global" not in runner._telemetry

    def test_recolectar_xml_invalido(self, cfg: Configuration, tmp_path: Path) -> None:
        runner = PipelineRunner(cfg, mode="check", files=[])
        runner.cfg.ura_root = tmp_path
        (tmp_path / "coverage.xml").write_text("no es xml")
        runner._recolectar_coverage()
        assert runner._telemetry["coverage_global"] == 0


class TestPhaseCommitADR221:
    def test_desactivado_por_defecto(self, cfg: Configuration, monkeypatch) -> None:
        monkeypatch.delenv("URA_TUNELADORA_AUTO_COMMIT", raising=False)
        runner = PipelineRunner(cfg, mode="gate", files=[])
        results = runner.phase_commit()
        assert results[0].status == Status.SKIP

    def test_activado_con_env(self, cfg: Configuration, monkeypatch) -> None:
        monkeypatch.setenv("URA_TUNELADORA_AUTO_COMMIT", "1")
        runner = PipelineRunner(cfg, mode="gate", files=[])
        runner.cfg.auto_commit = True
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout="committed", stderr="")
            results = runner.phase_commit()
        assert results[0].status == Status.OK
        assert m_run.call_count == 2  # git add + git commit

    def test_impl_no_gate_skip(self, cfg: Configuration) -> None:
        runner = PipelineRunner(cfg, mode="check", files=[])
        results = runner._phase_commit_impl()
        assert results[0].status == Status.SKIP

    def test_impl_auto_commit_false(self, cfg: Configuration) -> None:
        runner = PipelineRunner(cfg, mode="gate", files=[])
        runner.cfg.auto_commit = False
        results = runner._phase_commit_impl()
        assert results[0].status == Status.SKIP

    def test_impl_nada_que_commitear_ok(self, cfg: Configuration) -> None:
        runner = PipelineRunner(cfg, mode="gate", files=[])
        runner.cfg.auto_commit = True
        add_ok = mock.Mock(returncode=0, stdout="", stderr="")
        commit_nada = mock.Mock(returncode=1, stdout="nothing to commit", stderr="")
        with mock.patch("subprocess.run", side_effect=[add_ok, commit_nada]) as m_run:
            results = runner._phase_commit_impl()
        assert results[0].status == Status.OK
        assert m_run.call_count == 2

    def test_impl_error_warn(self, cfg: Configuration) -> None:
        runner = PipelineRunner(cfg, mode="gate", files=[])
        runner.cfg.auto_commit = True
        with mock.patch("subprocess.run", side_effect=OSError("boom")):
            results = runner._phase_commit_impl()
        assert results[0].status == Status.WARN
