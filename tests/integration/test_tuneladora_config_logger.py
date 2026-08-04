"""Tests para logger.py y config.py de la tuneladora."""
from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.logger import Logger


class TestLogger:
    def test_escribe_archivo_y_stream(self, tmp_path: Path) -> None:
        stream = io.StringIO()
        log = Logger(tmp_path / "logs" / "t.log", stream=stream)
        log.info("mensaje de prueba")
        assert "mensaje de prueba" in stream.getvalue()
        content = (tmp_path / "logs" / "t.log").read_text()
        assert "mensaje de prueba" in content
        assert "INFO" in content

    def test_niveles(self, tmp_path: Path) -> None:
        stream = io.StringIO()
        log = Logger(tmp_path / "t.log", stream=stream)
        log.warning("w")
        log.warn("w2")
        log.error("e")
        log.debug("d")
        out = stream.getvalue()
        assert "WARNING" in out
        assert "ERROR" in out
        assert "DEBUG" in out

    def test_permiso_denegado_no_crashea(self, tmp_path: Path) -> None:
        stream = io.StringIO()
        log = Logger(tmp_path / "t.log", stream=stream)
        with mock.patch("pathlib.Path.open", side_effect=PermissionError("ro")):
            log.info("x")  # no debe lanzar
        assert "x" in stream.getvalue()

    def test_report_formateado(self, tmp_path: Path) -> None:
        stream = io.StringIO()
        log = Logger(tmp_path / "t.log", stream=stream)
        log.report("Titulo", ["linea1", "linea2"])
        out = stream.getvalue()
        assert "Titulo" in out
        assert "linea1" in out
        assert "═" in out

    def test_timestamp_formato(self, tmp_path: Path) -> None:
        stream = io.StringIO()
        log = Logger(tmp_path / "t.log", stream=stream)
        log.info("m")
        assert "[" in stream.getvalue()


class TestConfigPyproject:
    def test_carga_valores(self, tmp_path: Path, monkeypatch) -> None:
        cfg = Configuration()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.tuneladora]\nllm-fallback-model = "test-model"\nunsafe-fixes = false\n'
        )
        monkeypatch.setattr(cfg, "ura_root", tmp_path)
        monkeypatch.setattr(cfg, "llm_fallback_model", "original")
        monkeypatch.setattr(cfg, "unsafe_fixes", True)
        cfg._load_from_pyproject()
        assert cfg.llm_fallback_model == "test-model"
        assert cfg.unsafe_fixes is False

    def test_sin_pyproject(self, tmp_path: Path, monkeypatch) -> None:
        cfg = Configuration()
        monkeypatch.setattr(cfg, "ura_root", tmp_path)
        cfg._load_from_pyproject()  # no debe lanzar

    def test_pyproject_invalido(self, tmp_path: Path, monkeypatch) -> None:
        cfg = Configuration()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.tuneladora\nno valido")
        monkeypatch.setattr(cfg, "ura_root", tmp_path)
        cfg._load_from_pyproject()  # no debe lanzar

    def test_propiedades_rutas(self, tmp_path: Path) -> None:
        cfg = Configuration()
        cfg.log_dir = tmp_path / "logs"
        cfg.nervioso = tmp_path / "nervioso"
        assert cfg.log_file == tmp_path / "logs" / "tuneladora.log"
        assert cfg.sistema_map == tmp_path / "nervioso" / "sistema_map.json"
        assert cfg.delta_snapshot_file == tmp_path / "nervioso" / "delta_snapshots" / "ultimo_ciclo.json"
