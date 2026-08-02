"""Tests for scripts/pro/reglas_loader.py."""
import json

from scripts.pro.reglas_loader import _reglas_fallback, cargar_reglas, guardar_reglas


class TestReglasLoader:
    def test_fallback_structure(self):
        reglas = _reglas_fallback()
        assert len(reglas) == 1
        assert reglas[0]["id"] == "builtin_fix_import_os"

    def test_cargar_reglas_sin_archivo(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.pro.reglas_loader.REGLAS_PATH", tmp_path / "no_existe.json")
        result = cargar_reglas()
        assert "reglas" in result
        assert len(result["reglas"]) >= 1

    def test_cargar_reglas_con_archivo(self, tmp_path, monkeypatch):
        reglas_file = tmp_path / "reglas.json"
        reglas_file.write_text(json.dumps({"reglas": [{"id": "custom"}], "ultima_actualizacion": "2024-01-01"}))
        monkeypatch.setattr("scripts.pro.reglas_loader.REGLAS_PATH", reglas_file)
        result = cargar_reglas()
        assert result["reglas"][0]["id"] == "custom"

    def test_guardar_reglas(self, tmp_path, monkeypatch):
        reglas_file = tmp_path / "reglas.json"
        monkeypatch.setattr("scripts.pro.reglas_loader.REGLAS_PATH", reglas_file)
        data = {"reglas": [{"id": "test"}], "ultima_actualizacion": "2024-01-01"}
        guardar_reglas(data)
        assert reglas_file.exists()
        loaded = json.loads(reglas_file.read_text())
        assert loaded["reglas"][0]["id"] == "test"
