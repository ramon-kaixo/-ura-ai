#!/usr/bin/env python3
"""Cobertura 100x100 de motor/core/agents/orquestador.py."""

import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
import sys
import ast

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.agents.orquestador import AgenteOrquestador


class TestAgenteOrquestadorInit:
    """Tests para inicialización."""

    @pytest.mark.unit
    def test_modelo_default(self):
        """Verifica modelo por defecto."""
        agente = AgenteOrquestador()
        assert agente.MODELO == "qwen3.6:27b"


class TestAgenteOrquestadorDecidir:
    """Tests para método decidir()."""

    @pytest.mark.unit
    def test_decidir_ram_alta_pausar(self):
        """RAM > 85% -> PAUSAR."""
        agente = AgenteOrquestador()
        telemetria = {"hardware": {"ram_pct": 90}, "f821": 0}
        conciencia = {"estado_general": "ok"}
        
        accion, razon = agente.decidir(telemetria, conciencia)
        
        assert accion == "PAUSAR"
        assert "RAM al 90%" in razon

    @pytest.mark.unit
    def test_decidir_ram_limite_exacto_85(self):
        """RAM = 85% -> NO pausa (es > 85, no >=)."""
        agente = AgenteOrquestador()
        telemetria = {"hardware": {"ram_pct": 85}, "f821": 0}
        conciencia = {"estado_general": "ok"}
        
        accion, razon = agente.decidir(telemetria, conciencia)
        
        # 85 no es > 85, así que no pausa
        assert accion != "PAUSAR"

    @pytest.mark.unit
    def test_decidir_f821_alto_reparar(self):
        """F821 > 10 -> REPARAR."""
        agente = AgenteOrquestador()
        telemetria = {"hardware": {"ram_pct": 50}, "f821": 15}
        conciencia = {"estado_general": "ok"}
        
        accion, razon = agente.decidir(telemetria, conciencia)
        
        assert accion == "REPARAR"
        assert "15 F821 detectados" in razon

    @pytest.mark.unit
    def test_decidir_f821_limite_exacto_10(self):
        """F821 = 10 -> NO repara (es > 10, no >=)."""
        agente = AgenteOrquestador()
        telemetria = {"hardware": {"ram_pct": 50}, "f821": 10}
        conciencia = {"estado_general": "ok"}
        
        accion, razon = agente.decidir(telemetria, conciencia)
        
        assert accion != "REPARAR"

    @pytest.mark.unit
    def test_decidir_funciones_pendientes_refactorizar(self):
        """Funciones pendientes > 0 y RAM < 85 -> REFACTORIZAR."""
        agente = AgenteOrquestador()
        telemetria = {"hardware": {"ram_pct": 50}, "f821": 5}
        conciencia = {"estado_general": "ok"}
        
        with patch.object(AgenteOrquestador, '_contar_pendientes', return_value=5):
            accion, razon = agente.decidir(
                {"hardware": {"ram_pct": 50}, "f821": 5}, 
                {"estado_general": "ok"}
            )
        
        assert accion == "REFACTORIZAR"
        assert "5 funciones pendientes" in razon

    @pytest.mark.unit
    def test_decidir_funciones_pendientes_pero_ram_alta(self):
        """Funciones pendientes > 0 PERO RAM > 85 -> PAUSAR (prioridad RAM)."""
        agente = AgenteOrquestador()
        
        with patch.object(AgenteOrquestador, '_contar_pendientes', return_value=10):
            accion, razon = agente.decidir(
                {"hardware": {"ram_pct": 90}, "f821": 0}, 
                {"estado_general": "ok"}
            )
        
        assert accion == "PAUSAR"
        assert "RAM al 90%" in razon

    @pytest.mark.unit
    def test_decidir_sistema_estable_esperar(self):
        """Sin condiciones -> ESPERAR."""
        agente = AgenteOrquestador()
        
        with patch.object(AgenteOrquestador, '_contar_pendientes', return_value=0):
            accion, razon = agente.decidir(
                {"hardware": {"ram_pct": 50}, "f821": 0}, 
                {"estado_general": "ok"}
            )
        
        assert accion == "ESPERAR"
        assert "Sistema estable" in razon


class TestAgenteOrquestadorContarPendientes:
    """Tests para _contar_pendientes()."""

    @pytest.mark.unit
    def test_contar_pendientes_archivo_con_funcion_larga(self, tmp_path):
        """Cuenta función > 80 líneas."""
        # Crear archivo temporal con función larga
        test_file = tmp_path / "test_largo.py"
        funcion_larga = "def funcion_larga():\n" + "\n".join([f"    x = {i}" for i in range(90)]) + "\n    return x"
        test_file.write_text(funcion_larga)
        
        with patch('motor.core.agents.orquestador.URA_ROOT', tmp_path):
            agente = AgenteOrquestador()
            count = agente._contar_pendientes()
            assert count >= 1

    @pytest.mark.unit
    def test_contar_pendientes_ignora_venv(self, tmp_path):
        """Verifica que ignora .venv."""
        venv_dir = tmp_path / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        test_file = venv_dir / "test.py"
        test_file.write_text("def funcion_larga():\n" + "\n".join([f"    x = {i}" for i in range(90)]) + "\n    return x")
        
        # También crear archivo normal
        normal_file = tmp_path / "normal.py"
        normal_file.write_text("def funcion_larga():\n" + "\n".join([f"    x = {i}" for i in range(90)]) + "\n    return x")
        
        with patch('motor.core.agents.orquestador.URA_ROOT', tmp_path):
            agente = AgenteOrquestador()
            count = agente._contar_pendientes()
            assert count == 1  # Solo cuenta el archivo normal

    @pytest.mark.unit
    def test_contar_pendientes_ignora_git(self, tmp_path):
        """Verifica que ignora .git."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir(parents=True)
        test_file = git_dir / "test.py"
        test_file.write_text("def funcion_larga():\n" + "\n".join([f"    x = {i}" for i in range(90)]) + "\n    return x")
        
        with patch('motor.core.agents.orquestador.URA_ROOT', tmp_path):
            agente = AgenteOrquestador()
            count = agente._contar_pendientes()
            assert count == 0

    @pytest.mark.unit
    def test_contar_pendientes_funcion_corta_no_cuenta(self, tmp_path):
        """Función <= 80 líneas no cuenta."""
        test_file = tmp_path / "corta.py"
        test_file.write_text("def corta():\n    x = 1\n    return x")
        
        with patch('motor.core.agents.orquestador.URA_ROOT', tmp_path):
            agente = AgenteOrquestador()
            count = agente._contar_pendientes()
            assert count == 0

    @pytest.mark.unit
    def test_contar_pendientes_syntax_error(self, tmp_path):
        """Maneja error de sintaxis sin fallar."""
        test_file = tmp_path / "syntax_error.py"
        test_file.write_text("def funcion(\n    return 1")  # Sintaxis inválida
        
        with patch('motor.core.agents.orquestador.URA_ROOT', tmp_path):
            agente = AgenteOrquestador()
            count = agente._contar_pendientes()
            # No debe fallar, solo log warning
            assert count >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
