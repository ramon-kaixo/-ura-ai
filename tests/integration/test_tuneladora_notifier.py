"""Tests para scripts/pro/tuneladora/notifier.py (Gap #3)."""
from __future__ import annotations

import io
from pathlib import Path
from unittest import mock

import pytest

import time

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.notifier import (
    _construir_mensaje,
    _notificar_log,
    _notificar_memoria,
    _notificar_systemd,
    _notificar_terminal,
    notificar_fallo,
)
from scripts.pro.tuneladora.pipeline.runner import PipelineRunner
from scripts.pro.tuneladora.pipeline.tools.base import Status


def _reporte_fail() -> dict:
    return {
        "verdict": "FAIL",
        "summary": "pipeline rechazado",
        "files": ["a.py"],
        "timestamp": "2026-08-05T00:00:00",
        "mode": "check",
    }


class TestConstruirMensaje:
    def test_incluye_campos(self) -> None:
        msg = _construir_mensaje(_reporte_fail())
        assert "FAIL" in msg
        assert "pipeline rechazado" in msg
        assert "1" in msg


class TestNotificarLog:
    def test_crea_failures_log(self, tmp_path: Path) -> None:
        _notificar_log("[FAIL] mensaje", tmp_path)
        log = tmp_path / "FAILURES.log"
        assert log.exists()
        content = log.read_text()
        assert "mensaje" in content
        assert "FAIL" in content

    def test_append_no_sobrescribe(self, tmp_path: Path) -> None:
        _notificar_log("[FAIL] primero", tmp_path)
        _notificar_log("[FAIL] segundo", tmp_path)
        content = (tmp_path / "FAILURES.log").read_text()
        assert content.count("FAIL") == 2


class TestNotificarMemoria:
    def test_guarda_episode(self) -> None:
        store = mock.Mock()
        with mock.patch(
            "motor.intelligence.memory.episodic.EpisodeStore",
            return_value=store,
        ):
            _notificar_memoria("mensaje", _reporte_fail())
        store.store.assert_called_once()
        episode = store.store.call_args[0][0]
        assert "pipeline_fallo" in episode.tags
        assert episode.payload == "mensaje"
        assert episode.metadata["verdict"] == "FAIL"

    def test_falla_silencioso(self) -> None:
        with mock.patch(
            "motor.intelligence.memory.episodic.EpisodeStore",
            mock.Mock(side_effect=RuntimeError("boom")),
        ), mock.patch(
            "scripts.pro.tuneladora.notifier._notificar_log"
        ), mock.patch(
            "scripts.pro.tuneladora.notifier._notificar_terminal"
        ):
            notificar_fallo(_reporte_fail(), report_dir=Path("/tmp/ura_no_dir"))  # no debe lanzar


class TestNotificarTerminal:
    def test_tty_escribe_rojo(self) -> None:
        stream = io.StringIO()
        stream.isatty = lambda: True
        _notificar_terminal("alerta", stream)
        assert "\033[91m" in stream.getvalue()

    def test_no_tty_no_escribe(self) -> None:
        stream = io.StringIO()
        stream.isatty = lambda: False
        _notificar_terminal("alerta", stream)
        assert stream.getvalue() == ""


class TestNotificarSystemd:
    def test_llama_systemd_cat(self) -> None:
        with mock.patch("subprocess.run") as m_run:
            _notificar_systemd("msg")
        m_run.assert_called_once()
        assert "systemd-cat" in m_run.call_args[0][0]

    def test_sin_systemd_cat_silencioso(self) -> None:
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            _notificar_systemd("msg")  # no debe lanzar


class TestNotificarFallo:
    def test_notifica_todos_los_canales(self, tmp_path: Path) -> None:
        with mock.patch(
            "scripts.pro.tuneladora.notifier._notificar_systemd"
        ) as m_sys, mock.patch(
            "scripts.pro.tuneladora.notifier._notificar_memoria"
        ) as m_mem, mock.patch(
            "scripts.pro.tuneladora.notifier._notificar_terminal"
        ) as m_term:
            ok = notificar_fallo(_reporte_fail(), report_dir=tmp_path)
        assert ok is True
        m_sys.assert_called_once()
        m_mem.assert_called_once()
        m_term.assert_called_once()
        assert (tmp_path / "FAILURES.log").exists()

    def test_canales_no_bloquean(self, tmp_path: Path) -> None:
        with mock.patch(
            "scripts.pro.tuneladora.notifier._notificar_log",
            side_effect=OSError("ro"),
        ), mock.patch(
            "scripts.pro.tuneladora.notifier._notificar_memoria",
            side_effect=RuntimeError("boom"),
        ), mock.patch("scripts.pro.tuneladora.notifier._notificar_terminal"):
            ok = notificar_fallo(_reporte_fail(), report_dir=tmp_path)
        assert ok is False  # log y memoria fallaron; terminal no cuenta


class TestIntegracionRunner:
    def _runner(self, tmp_path: Path) -> PipelineRunner:
        cfg = Configuration()
        cfg.ura_root = tmp_path
        return PipelineRunner(cfg, mode="check", files=["a.py"])

    def test_finish_genera_reporte_y_notifica_fail(self, tmp_path: Path) -> None:
        cfg = Configuration()
        cfg.ura_root = tmp_path
        runner = PipelineRunner(cfg, mode="check", files=["a.py"])
        runner._sofia_report = mock.Mock()
        runner._sofia_report.n_criticos = 0
        runner._sofia_report.n_advertencias = 0
        runner._telemetry = {"head": "abc"}
        with mock.patch.object(runner, "episodic"), mock.patch.object(
            runner, "ltm"
        ), mock.patch("scripts.pro.tuneladora.pipeline.runner._change_log"), mock.patch(
            "scripts.pro.tuneladora.pipeline.runner._auditoria_continua"
        ), mock.patch(
            "scripts.pro.tuneladora.notifier.notificar_fallo"
        ) as m_notificar:
            runner._finish("ep-1", Status.FAIL, "boom", time.monotonic() - 0.5)
        reportes = list((tmp_path / "data" / "tuneladora_reports").glob("ep-1.json"))
        assert len(reportes) == 1
        m_notificar.assert_called_once()
        assert m_notificar.call_args[0][0]["verdict"] == "FAIL"

    def test_finish_ok_no_notifica(self, tmp_path: Path) -> None:
        cfg = Configuration()
        cfg.ura_root = tmp_path
        runner = PipelineRunner(cfg, mode="check", files=[])
        runner._sofia_report = mock.Mock()
        runner._sofia_report.n_criticos = 0
        runner._sofia_report.n_advertencias = 0
        runner._telemetry = {"head": "abc"}
        with mock.patch.object(runner, "episodic"), mock.patch.object(
            runner, "ltm"
        ), mock.patch("scripts.pro.tuneladora.pipeline.runner._change_log"), mock.patch(
            "scripts.pro.tuneladora.pipeline.runner._auditoria_continua"
        ), mock.patch(
            "scripts.pro.tuneladora.notifier.notificar_fallo"
        ) as m_notificar:
            runner._finish("ep-2", Status.OK, "ok", time.monotonic() - 0.5)
        m_notificar.assert_not_called()
