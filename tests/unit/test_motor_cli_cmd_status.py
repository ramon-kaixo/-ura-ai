"""Tests para motor/cli/cmd_status.py — estado, cross, trend, graph, perf, summarise."""

import json
from pathlib import Path
from unittest import mock

import pytest

from motor.cli import cmd_status
from motor.core.executor import ProcessResult


def _res(returncode: int = 0, stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(ok=returncode == 0, cmd=[], returncode=returncode,
                         stdout=stdout, stderr=stderr)


@pytest.fixture
def config(tmp_path: Path) -> mock.Mock:
    cfg = mock.Mock()
    cfg.deploy_dir = str(tmp_path)
    return cfg


class TestStatus:
    def test_sin_estado(self, config: mock.Mock) -> None:
        fake_exec = mock.Mock()
        fake_exec.run.return_value = _res(stdout="python3\npython3\nopencode\n")
        with mock.patch("motor.cli.cmd_status._executor", fake_exec):
            assert cmd_status.cmd_status(config) is None

    def test_con_estado(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_status.ARCHIVO_ESTADO).write_text(json.dumps({"health_score": 95}))
        fake_exec = mock.Mock()
        fake_exec.run.return_value = _res(stdout="python3\npython3\n")
        with mock.patch("motor.cli.cmd_status._executor", fake_exec):
            assert cmd_status.cmd_status(config) is None

    def test_gethostname_falla(self, config: mock.Mock) -> None:
        with mock.patch("motor.cli.cmd_status.socket.gethostname", side_effect=OSError("x")), \
                mock.patch("motor.cli.cmd_status.log.debug"), \
                mock.patch("motor.cli.cmd_status._executor") as fake_exec:
            fake_exec.run.return_value = _res(stdout="")
            assert cmd_status.cmd_status(config) is None

    def test_ps_falla(self, config: mock.Mock) -> None:
        fake_exec = mock.Mock()
        fake_exec.run.side_effect = RuntimeError("boom")
        with mock.patch("motor.cli.cmd_status._executor", fake_exec), \
                mock.patch("motor.cli.cmd_status.log.debug"):
            assert cmd_status.cmd_status(config) is None


class TestCross:
    def test_ok(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_status.ARCHIVO_ESTADO).write_text(json.dumps({"health_score": 88}))
        fake_exec = mock.Mock()
        fake_exec.run.return_value = _res(stdout=json.dumps({"health_score": 77}))
        with mock.patch("motor.cli.cmd_status._executor", fake_exec):
            assert cmd_status.cmd_cross(config) is None

    def test_remoto_error(self, config: mock.Mock) -> None:
        fake_exec = mock.Mock()
        fake_exec.run.return_value = _res(returncode=1, stderr="ssh fail")
        with mock.patch("motor.cli.cmd_status._executor", fake_exec):
            assert cmd_status.cmd_cross(config) is None

    def test_remoto_excepcion(self, config: mock.Mock) -> None:
        fake_exec = mock.Mock()
        fake_exec.run.side_effect = TimeoutError("timeout")
        with mock.patch("motor.cli.cmd_status._executor", fake_exec):
            assert cmd_status.cmd_cross(config) is None


class TestTrend:
    def test_sin_archivo(self, config: mock.Mock) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_status.cmd_trend(config)
        assert exc.value.code == 1

    def test_con_archivo(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_status.ARCHIVO_TRENDS).write_text(
            json.dumps({"health": 90}) + "\n" + json.dumps({"health": 91}) + "\n",
        )
        assert cmd_status.cmd_trend(config) is None


class TestGraph:
    def test_sin_archivo(self, config: mock.Mock) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_status.cmd_graph(config)
        assert exc.value.code == 1

    def test_pocas_lineas(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_status.ARCHIVO_TRENDS).write_text(json.dumps({"health": 90}) + "\n")
        with pytest.raises(SystemExit) as exc:
            cmd_status.cmd_graph(config)
        assert exc.value.code == 1

    def test_ok(self, config: mock.Mock, tmp_path: Path) -> None:
        lines = [json.dumps({"health": h, "ts": "2026-01-01T00:00:00"}) for h in (92, 95, 98)]
        (tmp_path / cmd_status.ARCHIVO_TRENDS).write_text("\n".join(lines) + "\n")
        assert cmd_status.cmd_graph(config) is None


class TestPerf:
    def test_sin_archivo(self, config: mock.Mock) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_status.cmd_perf(config)
        assert exc.value.code == 1

    def test_sin_perf(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_status.ARCHIVO_TRENDS).write_text(json.dumps({"health": 90}) + "\n")
        with pytest.raises(SystemExit) as exc:
            cmd_status.cmd_perf(config)
        assert exc.value.code == 1

    def test_ok(self, config: mock.Mock, tmp_path: Path) -> None:
        lines = [json.dumps({"perf": {"scan_s": 1, "gen_s": 2}}) for _ in range(3)]
        (tmp_path / cmd_status.ARCHIVO_TRENDS).write_text("\n".join(lines) + "\n")
        assert cmd_status.cmd_perf(config) is None


class TestSummarise:
    def test_sin_estado(self, config: mock.Mock) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_status.cmd_summarise(config)
        assert exc.value.code == 1

    def test_con_estado(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_status.ARCHIVO_ESTADO).write_text(json.dumps({
            "health_score": 90,
            "servicios": {"a": "inactive", "b": "failed", "c": "active"},
            "recursos": {"ram_pct": 30, "disk_pct": 40},
        }))
        with mock.patch("motor.cli.cmd_status.QdrantClient.instancia", return_value=mock.Mock()):
            assert cmd_status.cmd_summarise(config) is None

    def test_con_trends(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_status.ARCHIVO_ESTADO).write_text(json.dumps({
            "health_score": 90,
            "servicios": {},
            "recursos": {"ram_pct": 30, "disk_pct": 40},
        }))
        (tmp_path / cmd_status.ARCHIVO_TRENDS).write_text(
            json.dumps({"perf": {"scan_s": 5}}) + "\n",
        )
        with mock.patch("motor.cli.cmd_status.QdrantClient.instancia", return_value=mock.Mock()):
            assert cmd_status.cmd_summarise(config) is None
