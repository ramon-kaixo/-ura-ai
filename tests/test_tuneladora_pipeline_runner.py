"""Tests for PipelineRunner (scripts/pro/tuneladora/pipeline/runner.py)."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.pipeline.runner import PipelineRunner, _free_disk_gb
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
        ):
            runner._acquire_lock.return_value = True
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
