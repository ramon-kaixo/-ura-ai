"""Tests para motor/cli/cmd_utils.py — notify, qdrant backup, bench."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

import pytest

from motor.cli import cmd_utils


@pytest.fixture
def config(tmp_path: Path) -> mock.Mock:
    cfg = mock.Mock()
    cfg.deploy_dir = str(tmp_path)
    return cfg


class TestNotify:
    def test_sin_estado(self, config: mock.Mock) -> None:
        with pytest.raises(SystemExit) as exc:
            cmd_utils.cmd_notify(config)
        assert exc.value.code == 0

    def test_health_bajo(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_utils.ARCHIVO_ESTADO).write_text(json.dumps({"health_score": 50}))
        with mock.patch("motor.cli.cmd_utils._executor") as fake_exec:
            cmd_utils.cmd_notify(config)
        fake_exec.run.assert_called_once()

    def test_health_alto_con_incidentes(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_utils.ARCHIVO_ESTADO).write_text(json.dumps({"health_score": 100}))
        (tmp_path / cmd_utils.ARCHIVO_DIAGNOSTICO).write_text(json.dumps({"incidentes": [1]}))
        with mock.patch("motor.cli.cmd_utils._executor") as fake_exec:
            cmd_utils.cmd_notify(config)
        fake_exec.run.assert_called_once()

    def test_health_alto_sin_incidentes(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_utils.ARCHIVO_ESTADO).write_text(json.dumps({"health_score": 100}))
        with mock.patch("motor.cli.cmd_utils._executor") as fake_exec:
            cmd_utils.cmd_notify(config)
        fake_exec.run.assert_not_called()

    def test_notify_send_ausente(self, config: mock.Mock, tmp_path: Path) -> None:
        (tmp_path / cmd_utils.ARCHIVO_ESTADO).write_text(json.dumps({"health_score": 10}))
        fake_exec = mock.Mock()
        fake_exec.run.side_effect = FileNotFoundError("no")
        with mock.patch("motor.cli.cmd_utils._executor", fake_exec), \
                mock.patch("motor.cli.cmd_utils.log.debug") as debug:
            cmd_utils.cmd_notify(config)
        debug.assert_called_once()


class TestQdrantBackup:
    def test_no_disponible(self, config: mock.Mock) -> None:
        fake_qdrant = mock.Mock()
        fake_qdrant.disponible = False
        with mock.patch("motor.cli.cmd_utils.QdrantClient.instancia", return_value=fake_qdrant):
            with pytest.raises(SystemExit) as exc:
                cmd_utils.cmd_qdrant_backup(config)
        assert exc.value.code == 1

    def test_backup_ok(self, config: mock.Mock, tmp_path: Path) -> None:
        fake_qdrant = mock.Mock()
        fake_qdrant.disponible = True
        fake_qdrant.buscar_incidentes.return_value = [{"id": 1}]
        with mock.patch("motor.cli.cmd_utils.QdrantClient.instancia", return_value=fake_qdrant):
            cmd_utils.cmd_qdrant_backup(config)
        backups = list(tmp_path.glob("qdrant_backup_*.json"))
        assert len(backups) == 1
        data = json.loads(backups[0].read_text())
        assert data["total"] == 1
        assert data["incidentes"] == [{"id": 1}]
        assert data["exported_at"].endswith("+00:00Z")


def test_cmd_bench() -> None:
    assert cmd_utils.cmd_bench() is None
    assert cmd_utils.cmd_bench(mock.Mock(), ["a"]) is None
