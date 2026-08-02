"""Tests for core/agents/conciencia.py."""


import pytest

from core.agents.conciencia import Conciencia


class TestConciencia:
    @pytest.fixture(autouse=True)
    def tmp_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Conciencia, "PATH", tmp_path / "conciencia.json")
        return tmp_path

    def test_nuevo(self):
        data = Conciencia._nuevo()
        assert data["estado_general"] == "ok"
        assert data["nivel_error"] == 0
        assert "orquestador" in data["procesos"]
        assert len(data["contexto_global"]["errores_acumulados"]) == 0

    def test_leer_no_existe(self):
        data = Conciencia.leer()
        assert data["estado_general"] == "ok"
        assert data["nivel_error"] == 0

    def test_escribir_y_leer(self):
        data = Conciencia._nuevo()
        data["estado_general"] = "warning"
        Conciencia.escribir(data)
        assert Conciencia.PATH.exists()
        leido = Conciencia.leer()
        assert leido["estado_general"] == "warning"

    def test_actualizar_proceso(self):
        Conciencia.actualizar_proceso("orquestador", "activo")
        data = Conciencia.leer()
        assert data["procesos"]["orquestador"]["estado"] == "activo"
        assert "ultima_actualizacion" in data["procesos"]["orquestador"]

    def test_registrar_error(self):
        Conciencia.registrar_error(2, "test error")
        data = Conciencia.leer()
        assert data["nivel_error"] == 2
        assert len(data["contexto_global"]["errores_acumulados"]) == 1
        assert data["contexto_global"]["errores_acumulados"][0]["mensaje"] == "test error"

    def test_registrar_error_trunca(self):
        for i in range(55):
            Conciencia.registrar_error(1, f"error {i}")
        data = Conciencia.leer()
        assert len(data["contexto_global"]["errores_acumulados"]) == 50

    def test_nivel_error(self):
        assert Conciencia.nivel_error() == 0
        Conciencia.registrar_error(3, "critical")
        assert Conciencia.nivel_error() == 3

    def test_leer_json_invalido(self, monkeypatch, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json")
        monkeypatch.setattr(Conciencia, "PATH", bad)
        data = Conciencia.leer()
        assert data["estado_general"] == "ok"  # fallback a _nuevo
