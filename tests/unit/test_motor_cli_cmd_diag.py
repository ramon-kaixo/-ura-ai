"""Tests para motor/cli/cmd_diag.py — diagnóstico, preflight, tendencias."""

import json
from pathlib import Path
from unittest import mock

import pytest

from motor.cli import cmd_diag
from motor.core.executor import ProcessResult


def _res(stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(ok=True, cmd=[], returncode=0, stdout=stdout, stderr=stderr)


@pytest.fixture
def config(tmp_path: Path) -> mock.Mock:
    cfg = mock.Mock()
    cfg.deploy_dir = str(tmp_path)
    return cfg


class TestHistory:
    def test_no_disponible(self, config: mock.Mock) -> None:
        fake_qdrant = mock.Mock()
        fake_qdrant.disponible = False
        with mock.patch("motor.cli.cmd_diag.QdrantClient.instancia", return_value=fake_qdrant):
            with pytest.raises(SystemExit) as exc:
                cmd_diag.cmd_history(config)
        assert exc.value.code == 1

    def test_ok(self, config: mock.Mock) -> None:
        fake_qdrant = mock.Mock()
        fake_qdrant.disponible = True
        with mock.patch("motor.cli.cmd_diag.QdrantClient.instancia", return_value=fake_qdrant):
            cmd_diag.cmd_history(config)
        fake_qdrant.buscar_incidentes.assert_called_once_with(limit=50)


class TestCheck:
    def test_ok(self, config: mock.Mock) -> None:
        fake_pre = mock.Mock()
        fake_pre.ok = True
        with mock.patch("motor.cli.cmd_diag.ejecutar_preflight", return_value=fake_pre):
            with pytest.raises(SystemExit) as exc:
                cmd_diag.cmd_check(config)
        assert exc.value.code == 0

    def test_fail(self, config: mock.Mock) -> None:
        fake_pre = mock.Mock()
        fake_pre.ok = False
        with mock.patch("motor.cli.cmd_diag.ejecutar_preflight", return_value=fake_pre):
            with pytest.raises(SystemExit) as exc:
                cmd_diag.cmd_check(config)
        assert exc.value.code == 1


def test_verify(config: mock.Mock) -> None:
    with mock.patch("motor.cli.cmd_diag.ejecutar_verificacion") as ver:
        cmd_diag.cmd_verify(config)
    ver.assert_called_once_with(config, hubo_cambios=True)


class TestDetect:
    def test_sin_trends(self, config: mock.Mock) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_diag.cmd_detect(config)
        assert exc.value.code == 1

    def test_con_trends(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_diag.ARCHIVO_TRENDS).write_text(
            json.dumps({"health": 90, "ram_pct": 30}) + "\n" +
            json.dumps({"health": 80, "ram_pct": 40}) + "\n",
        )
        fake_cal = mock.Mock()
        with mock.patch("motor.cli.cmd_diag.Calibration", return_value=fake_cal):
            cmd_diag.cmd_detect(config)
        fake_cal.detect.assert_called_once()


class TestLearn:
    def test_sin_archivo(self, config: mock.Mock) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_diag.cmd_learn(config)
        assert exc.value.code == 1

    def test_vacio(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_diag.ARCHIVO_TRENDS).write_text("")
        with pytest.raises(SystemExit) as exc:
            cmd_diag.cmd_learn(config)
        assert exc.value.code == 1

    def test_pocas_lineas(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_diag.ARCHIVO_TRENDS).write_text("{}\n{}\n")
        with pytest.raises(SystemExit) as exc:
            cmd_diag.cmd_learn(config)
        assert exc.value.code == 1

    def test_con_tendencias(self, config: mock.Mock, tmp_path: Path) -> None:
        lineas = [{"health": h, "ram_pct": r, "disk_pct": d} for h, r, d in [
            (50, 20, 30), (60, 40, 40), (70, 60, 50),
        ]]
        (tmp_path / cmd_diag.ARCHIVO_TRENDS).write_text(
            "\n".join(json.dumps(l) for l in lineas) + "\n",
        )
        assert cmd_diag.cmd_learn(config) is None

    def test_tendencia_bajando(self, config: mock.Mock, tmp_path: Path) -> None:
        lineas = [{"health": h, "ram_pct": r, "disk_pct": d} for h, r, d in [
            (90, 60, 80), (70, 50, 60), (50, 40, 40),
        ]]
        (tmp_path / cmd_diag.ARCHIVO_TRENDS).write_text(
            "\n".join(json.dumps(l) for l in lineas) + "\n",
        )
        assert cmd_diag.cmd_learn(config) is None

    def test_disk_casi_lleno(self, config: mock.Mock, tmp_path: Path) -> None:
        lineas = [{"health": 50, "disk_pct": d} for d in (80, 90, 99)]
        (tmp_path / cmd_diag.ARCHIVO_TRENDS).write_text(
            "\n".join(json.dumps(l) for l in lineas) + "\n",
        )
        assert cmd_diag.cmd_learn(config) is None


class TestAlerta:
    def test_ok(self) -> None:
        with mock.patch("motor.cli.cmd_diag._executor") as fake_exec:
            fake_exec.run.return_value = _res(stdout="line ALERTA\nother\nerror line\n")
            cmd_diag.cmd_alerta(None)


class TestHealthCheck:
    def test_ok(self, config: mock.Mock, tmp_path: Path) -> None:
        fake_exec = mock.Mock()
        fake_exec.run.side_effect = lambda cmd, **kwargs: _res(stdout="active")
        fake_qdrant = mock.Mock()
        fake_qdrant.disponible = True
        (tmp_path / cmd_diag.ARCHIVO_ESTADO).write_text("{}")
        (tmp_path / cmd_diag.ARCHIVO_TRENDS).write_text("a\nb\n")
        with mock.patch("motor.cli.cmd_diag._executor", fake_exec), \
                mock.patch("motor.cli.cmd_diag.QdrantClient.instancia", return_value=fake_qdrant):
            assert cmd_diag.cmd_health_check(config) is None

    def test_excepcion_systemctl(self, config: mock.Mock, tmp_path: Path) -> None:
        fake_exec = mock.Mock()
        fake_exec.run.side_effect = RuntimeError("boom")
        fake_qdrant = mock.Mock()
        fake_qdrant.disponible = False
        with mock.patch("motor.cli.cmd_diag._executor", fake_exec), \
                mock.patch("motor.cli.cmd_diag.QdrantClient.instancia", return_value=fake_qdrant):
            assert cmd_diag.cmd_health_check(config) is None

    def test_excepcion_docker(self, config: mock.Mock, tmp_path: Path) -> None:
        def side_effect(cmd, **kwargs):  # noqa: ANN001, ANN202
            if "docker" in cmd:
                raise RuntimeError("no docker")
            return _res(stdout="inactive")
        fake_exec = mock.Mock()
        fake_exec.run.side_effect = side_effect
        fake_qdrant = mock.Mock()
        fake_qdrant.disponible = True
        with mock.patch("motor.cli.cmd_diag._executor", fake_exec), \
                mock.patch("motor.cli.cmd_diag.QdrantClient.instancia", return_value=fake_qdrant):
            assert cmd_diag.cmd_health_check(config) is None
