"""Tests para motor/cli/cmd_pipeline.py — pipeline, scan, diagnose, calibrate."""

import json
from pathlib import Path
from unittest import mock

import pytest

from motor.cli import cmd_pipeline
from motor.core.state import ScanResult


@pytest.fixture
def config(tmp_path: Path) -> mock.Mock:
    cfg = mock.Mock()
    cfg.deploy_dir = str(tmp_path)
    return cfg


def _scan_result(ok: bool = True) -> ScanResult:
    return ScanResult(ok=ok, timestamp="2026-01-01")


class TestPipeline:
    def test_ok(self, config: mock.Mock) -> None:
        orch = mock.Mock()
        orch.run.return_value = _scan_result(ok=True)
        with mock.patch("motor.cli.cmd_pipeline.Orchestrator", return_value=orch), \
                mock.patch("motor.cli.cmd_pipeline.sys.exit") as sys_exit:
            args = mock.Mock(dry_run=True)
            cmd_pipeline.cmd_pipeline(config, args)
        orch.run.assert_called_once_with(dry_run=True)
        sys_exit.assert_called_once_with(0)

    def test_fail(self, config: mock.Mock) -> None:
        orch = mock.Mock()
        orch.run.return_value = _scan_result(ok=False)
        with mock.patch("motor.cli.cmd_pipeline.Orchestrator", return_value=orch), \
                mock.patch("motor.cli.cmd_pipeline.sys.exit") as sys_exit:
            cmd_pipeline.cmd_pipeline(config, mock.Mock(dry_run=False))
        sys_exit.assert_called_once_with(1)


def test_scan(config: mock.Mock) -> None:
    sc = mock.Mock()
    with mock.patch("motor.cli.cmd_pipeline.Scanner", return_value=sc):
        cmd_pipeline.cmd_scan(config)
    sc.run.assert_called_once()


def test_diagnose(config: mock.Mock) -> None:
    qdrant = mock.Mock()
    diag = mock.Mock()
    with mock.patch("motor.cli.cmd_pipeline.QdrantClient.instancia", return_value=qdrant), \
            mock.patch("motor.cli.cmd_pipeline.Diagnostico", return_value=diag):
        cmd_pipeline.cmd_diagnose(config)
    diag.run.assert_called_once()
    scan = diag.run.call_args[0][0]
    assert scan.ok is True


class TestCalibrate:
    def test_baseline_sin_force(self, config: mock.Mock) -> None:
        cal = mock.Mock()
        cal.hay_baseline = True
        with mock.patch("motor.cli.cmd_pipeline.Calibration", return_value=cal), \
                mock.patch("motor.cli.cmd_pipeline.Scanner", return_value=mock.Mock()), \
                mock.patch("motor.cli.cmd_pipeline.sys.exit") as sys_exit:
            cmd_pipeline.cmd_calibrate(config, mock.Mock(force=False))
        sys_exit.assert_called_once_with(1)

    def test_force_sin_trends(self, config: mock.Mock, tmp_path: Path) -> None:
        cal = mock.Mock()
        cal.hay_baseline = True
        sc = mock.Mock()
        sc.run.return_value = _scan_result()
        with mock.patch("motor.cli.cmd_pipeline.Calibration", return_value=cal), \
                mock.patch("motor.cli.cmd_pipeline.Scanner", return_value=sc):
            cmd_pipeline.cmd_calibrate(config, mock.Mock(force=True))
        cal.learn.assert_called_once()
        assert cal.learn.call_args[0][1] == []

    def test_con_trends(self, config: mock.Mock, tmp_path: Path) -> None:
        cal = mock.Mock()
        cal.hay_baseline = False
        sc = mock.Mock()
        sc.run.return_value = _scan_result()
        (tmp_path / cmd_pipeline.ARCHIVO_TRENDS).write_text(
            json.dumps({"health": 90}) + "\n",
        )
        with mock.patch("motor.cli.cmd_pipeline.Calibration", return_value=cal), \
                mock.patch("motor.cli.cmd_pipeline.Scanner", return_value=sc):
            cmd_pipeline.cmd_calibrate(config, mock.Mock(force=False))
        assert len(cal.learn.call_args[0][1]) == 1
