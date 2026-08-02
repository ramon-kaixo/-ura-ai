"""Tests for core/guardian_disco.py."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.guardian_disco import (
    calcular_hash,
    cargar_config,
    comparar,
    escanear,
    guardar_historial,
    guardar_snapshot,
    verificar_escritura,
)


@pytest.fixture
def aislar_paths(tmp_path, monkeypatch):
    """Aísla URA, snapshot y config en un directorio temporal."""
    monkeypatch.setattr("core.guardian_disco.URA", tmp_path)
    monkeypatch.setattr("core.guardian_disco.NERVIOSO", tmp_path / ".nervioso")
    monkeypatch.setattr("core.guardian_disco.SNAPSHOT", tmp_path / ".nervioso" / "hashes.json")
    monkeypatch.setattr("core.guardian_disco.HISTORIAL", tmp_path / ".nervioso" / "hashes_history.jsonl")
    monkeypatch.setattr("core.guardian_disco.CONFIG_PATH", tmp_path / ".nervioso" / "guardian_config.json")
    return tmp_path


class TestCalcularHash:
    def test_sha256_completo(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("print('hola')")
        h = calcular_hash(f)
        assert len(h) == 64

    def test_truncado(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x")
        assert len(calcular_hash(f, truncar=12)) == 12

    def test_determinista(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("mismo contenido")
        assert calcular_hash(f) == calcular_hash(f)


class TestComparar:
    def test_nuevo(self):
        cambios = comparar({}, {"a.py": "h1"})
        assert cambios == [{"file": "a.py", "status": "NUEVO", "hash": "h1"}]

    def test_modificado(self):
        cambios = comparar({"a.py": "h1"}, {"a.py": "h2"})
        assert cambios[0]["status"] == "MODIFICADO"
        assert cambios[0]["hash"] == "h2"

    def test_fantasma(self):
        cambios = comparar({"a.py": "h1"}, {})
        assert cambios == [{"file": "a.py", "status": "FANTASMA", "hash": "—"}]

    def test_sin_cambios(self):
        assert comparar({"a.py": "h1"}, {"a.py": "h1"}) == []


class TestVerificarEscritura:
    def test_coincide(self, aislar_paths, monkeypatch):
        (aislar_paths / "f.py").write_text("contenido")
        h = calcular_hash(aislar_paths / "f.py")
        monkeypatch.setattr("core.guardian_disco.cargar_config", lambda: {"hash_truncar": 64})
        assert verificar_escritura("f.py", h) is True

    def test_no_coincide(self, aislar_paths, monkeypatch):
        (aislar_paths / "f.py").write_text("contenido")
        monkeypatch.setattr("core.guardian_disco.cargar_config", lambda: {"hash_truncar": 64})
        assert verificar_escritura("f.py", "deadbeef") is False

    def test_fantasma(self, aislar_paths, monkeypatch):
        monkeypatch.setattr("core.guardian_disco.cargar_config", lambda: {"hash_truncar": 64})
        assert verificar_escritura("no_existe.py", "h") is False

    def test_usar_config_explicita(self, aislar_paths):
        (aislar_paths / "f.py").write_text("x")
        assert verificar_escritura("f.py", "y", config={"hash_truncar": 64}) is False


class TestCargarConfig:
    def test_crea_default_si_no_existe(self, aislar_paths):
        cfg = cargar_config()
        assert "patrones" in cfg
        assert "excluir" in cfg
        assert aislar_paths.joinpath(".nervioso", "guardian_config.json").exists()

    def test_lee_config_existente(self, aislar_paths):
        cfg_path = aislar_paths / ".nervioso" / "guardian_config.json"
        cfg_path.parent.mkdir(parents=True)
        cfg_path.write_text(json.dumps({"patrones": ["*.py"], "excluir": []}))
        assert cargar_config() == {"patrones": ["*.py"], "excluir": []}

    def test_config_corrupta_devuelve_default(self, aislar_paths):
        cfg_path = aislar_paths / ".nervioso" / "guardian_config.json"
        cfg_path.parent.mkdir(parents=True)
        cfg_path.write_text("{no es json")
        cfg = cargar_config()
        assert cfg["hash_truncar"] == 64


class TestGuardarSnapshot:
    def test_escribe_snapshot(self, aislar_paths):
        guardar_snapshot({"total": 1})
        snap = json.loads(aislar_paths.joinpath(".nervioso", "hashes.json").read_text())
        assert snap == {"total": 1}

    def test_no_deja_temp(self, aislar_paths):
        guardar_snapshot({"total": 1})
        assert not aislar_paths.joinpath(".nervioso", "hashes.tmp").exists()


class TestGuardarHistorial:
    def test_append_jsonl(self, aislar_paths):
        cambios = [
            {"file": "a.py", "status": "NUEVO", "hash": "h"},
            {"file": "b.py", "status": "MODIFICADO", "hash": "h"},
            {"file": "c.py", "status": "FANTASMA", "hash": "—"},
        ]
        guardar_historial(cambios, total=10)
        lineas = aislar_paths.joinpath(".nervioso", "hashes_history.jsonl").read_text().splitlines()
        assert len(lineas) == 1
        entry = json.loads(lineas[0])
        assert entry["nuevos"] == 1
        assert entry["modificados"] == 1
        assert entry["fantasmas"] == 1
        assert entry["total_archivos"] == 10

    def test_append_acumula(self, aislar_paths):
        guardar_historial([], total=1)
        guardar_historial([], total=2)
        lineas = aislar_paths.joinpath(".nervioso", "hashes_history.jsonl").read_text().splitlines()
        assert len(lineas) == 2


class TestEscanear:
    def test_respeta_patrones_y_exclusiones(self, aislar_paths, monkeypatch):
        (aislar_paths / "app.py").write_text("codigo")
        (aislar_paths / "app.json").write_text("{}")
        (aislar_paths / "nota.txt").write_text("no")
        (aislar_paths / ".venv" / "lib.py").mkdir(parents=True)
        (aislar_paths / ".venv" / "lib.py" / "x.py").write_text("venv")
        cfg = {"patrones": ["*.py", "*.json"], "excluir": [".venv"], "hash_truncar": 64}
        actual = escanear(cfg)
        assert "app.py" in actual
        assert "app.json" in actual
        assert "nota.txt" not in actual
        assert not any(".venv" in k for k in actual)

    def test_ignora_inaccesibles(self, aislar_paths, monkeypatch):
        (aislar_paths / "ok.py").write_text("x")
        cfg = {"patrones": ["*.py"], "excluir": [], "hash_truncar": 64}
        with patch("core.guardian_disco.calcular_hash", side_effect=PermissionError("denied")):
            assert escanear(cfg) == {}
