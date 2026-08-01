"""Tests for core/agents/orquestador.py."""

from unittest.mock import patch

import pytest

from core.agents.orquestador import AgenteOrquestador


class TestDecidir:
    def test_ram_saturada(self):
        orq = AgenteOrquestador()
        tele = {"hardware": {"ram_pct": 90}}
        conc = {}
        accion, razon = orq.decidir(tele, conc)
        assert accion == "PAUSAR"
        assert "RAM al 90%" in razon

    def test_f821_alto(self):
        orq = AgenteOrquestador()
        tele = {"hardware": {"ram_pct": 50}, "f821": 15}
        conc = {}
        accion, razon = orq.decidir(tele, conc)
        assert accion == "REPARAR"
        assert "15 F821" in razon

    def test_sistema_estable(self):
        orq = AgenteOrquestador()
        tele = {"hardware": {"ram_pct": 50}, "f821": 0}
        conc = {}
        with patch.object(orq, "_contar_pendientes", return_value=0):
            accion, razon = orq.decidir(tele, conc)
        assert accion == "ESPERAR"
        assert "Sistema estable" in razon

    def test_refactorizar(self):
        orq = AgenteOrquestador()
        tele = {"hardware": {"ram_pct": 50}, "f821": 0}
        conc = {}
        with patch.object(orq, "_contar_pendientes", return_value=5):
            accion, razon = orq.decidir(tele, conc)
        assert accion == "REFACTORIZAR"
        assert "5 funciones pendientes" in razon

    def test_ram_limite_85(self):
        orq = AgenteOrquestador()
        tele = {"hardware": {"ram_pct": 85}}
        conc = {}
        with patch.object(orq, "_contar_pendientes", return_value=0):
            accion, razon = orq.decidir(tele, conc)
        # 85% no es > 85, así que no pausa
        assert accion != "PAUSAR"

    def test_f821_default_alto(self):
        orq = AgenteOrquestador()
        tele = {"hardware": {"ram_pct": 50}}
        conc = {}
        # Sin f821 en telemetría, default es 99
        accion, razon = orq.decidir(tele, conc)
        assert accion == "REPARAR"
        assert "99 F821" in razon


class TestContarPendientes:
    def test_funcion_pequena_no_cuenta(self, tmp_path):
        f = tmp_path / "small.py"
        f.write_text("def foo():\n    pass\n")
        with patch("core.agents.orquestador.URA_ROOT", tmp_path):
            result = AgenteOrquestador._contar_pendientes()
            assert result == 0

    def test_funcion_grande_cuenta(self, tmp_path):
        # Función de más de 80 líneas
        lines = ["def big():"] + ["    x = 1"] * 82
        f = tmp_path / "big.py"
        f.write_text("\n".join(lines))
        with patch("core.agents.orquestador.URA_ROOT", tmp_path):
            result = AgenteOrquestador._contar_pendientes()
            assert result == 1

    def test_ignora_venv(self, tmp_path):
        f = tmp_path / ".venv" / "test.py"
        f.parent.mkdir()
        f.write_text("def big():\n" + "    x = 1\n" * 82)
        with patch("core.agents.orquestador.URA_ROOT", tmp_path):
            result = AgenteOrquestador._contar_pendientes()
            assert result == 0
