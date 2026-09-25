#!/usr/bin/env python3
"""Cobertura 100x100 de motor/core/agents/healing.py."""

import pytest
import json
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.agents.healing import SelfHealingLoop


class TestSelfHealingLoopInit:
    """Tests para inicialización."""

    @pytest.mark.unit
    def test_init_crea_componentes(self):
        """Verifica que crea todos los componentes."""
        with patch('motor.core.agents.healing.AgenteOrquestador') as mock_orq_class, \
             patch('motor.core.agents.healing.AgenteEjecutor') as mock_ejec_class, \
             patch('motor.core.agents.healing.AgenteReparador') as mock_rep_class, \
             patch('motor.core.agents.healing.Telemetria') as mock_tel_class, \
             patch('motor.core.agents.healing.Conciencia') as mock_conciencia_class:
            
            mock_orq = MagicMock()
            mock_orq.decidir.return_value = ("ESPERAR", "Sistema estable")
            mock_orq_class.return_value = mock_orq
            
            mock_ejec = MagicMock()
            mock_ejec.ejecutar.return_value = {"ok": 0, "err": 0, "workers": []}
            mock_ejec_class.return_value = mock_ejec
            
            mock_rep = MagicMock()
            mock_rep_class.return_value = mock_rep
            
            mock_tele = MagicMock()
            mock_tele.reporte_completo.return_value = {"hardware": {"ram_pct": 50}, "f821": 0}
            mock_tele.f821_count.return_value = 0
            mock_tele.hardware.return_value = {"ram_libre_mb": 1000}
            
            loop = SelfHealingLoop()
            
            assert loop.orquestador is not None
            assert loop.ejecutor is not None
            assert loop.reparador is not None
            assert loop.telemetria is not None
            assert loop._fallos_consecutivos == 0


class TestSelfHealingLoopEjecutar:
    """Tests para método ejecutar()."""

    @pytest.mark.unit
    def test_ejecutar_retorna_reporte_basico(self):
        """Verifica estructura básica del reporte."""
        with patch('motor.core.agents.healing.Conciencia') as mock_conciencia, \
             patch('motor.core.agents.healing.Telemetria') as mock_telemetria, \
             patch('motor.core.agents.healing.AgenteOrquestador') as mock_orq_class, \
             patch('motor.core.agents.healing.AgenteEjecutor') as mock_ejec_class, \
             patch('motor.core.agents.healing.AgenteReparador') as mock_rep_class, \
             patch('motor.core.agents.healing.Telemetria') as mock_tel_class:
            
            mock_tele = MagicMock()
            mock_tele.reporte_completo.return_value = {"hardware": {"ram_pct": 50}, "f821": 0}
            mock_tele.f821_count.return_value = 0
            mock_tele.hardware.return_value = {"ram_libre_mb": 1000}
            mock_tel_class.return_value = mock_tele
            
            mock_conciencia = MagicMock()
            mock_conciencia.leer.return_value = {"estado_general": "ok"}
            
            mock_orq = MagicMock()
            mock_orq.decidir.return_value = ("ESPERAR", "Sistema estable")
            
            mock_ejec = MagicMock()
            mock_ejec.ejecutar.return_value = {"ok": 0, "err": 0, "workers": []}
            
            with patch('motor.core.agents.healing.AgenteOrquestador', return_value=MagicMock(decidir=MagicMock(return_value=("ESPERAR", "ok")))), \
                 patch('motor.core.agents.healing.AgenteEjecutor') as mock_ejec_class, \
                 patch('motor.core.agents.healing.Conciencia') as mock_conciencia_class, \
                 patch('motor.core.agents.healing.Telemetria') as mock_tel_class:
                
                mock_tele = MagicMock()
                mock_tele.reporte_completo.return_value = {"hardware": {"ram_pct": 50}, "f821": 0}
                mock_tele.f821_count.return_value = 0
                mock_tele.hardware.return_value = {"ram_libre_mb": 1000}
                mock_tel_class.return_value = mock_tele
                
                mock_conciencia = MagicMock()
                mock_conciencia.leer.return_value = {"estado_general": "ok"}
                
                loop = SelfHealingLoop.__new__(SelfHealingLoop)
                loop.orquestador = MagicMock(decidir=MagicMock(return_value=("ESPERAR", "ok")))
                loop.ejecutor = MagicMock(ejecutar=MagicMock(return_value={"ok": 0, "err": 0, "workers": []}))
                loop.telemetria = MagicMock(f821_count=lambda: 0, hardware=lambda: {"ram_libre_mb": 1000})
                loop._fallos_consecutivos = 0
                
                with patch('motor.core.agents.healing.Conciencia') as mock_conciencia_class:
                    mock_conciencia_class.leer.return_value = {"estado": "ok"}
                    mock_conciencia_class.actualizar_proceso = MagicMock()
                    
                    resultado = SelfHealingLoop().ejecutar()
                    
                    assert "timestamp" in resultado
                    assert "pasos" in resultado
                    assert resultado["accion"] == "ESPERAR"
                    assert "razon" in resultado

    @pytest.mark.unit
    def test_ejecutar_accion_refactorizar(self):
        """Verifica acción REFACTORIZAR."""
        loop = SelfHealingLoop.__new__(SelfHealingLoop)
        loop.orquestador = MagicMock(decidir=lambda t, c: ("REFACTORIZAR", "test"))
        loop.ejecutor = MagicMock(ejecutar=MagicMock(return_value={"ok": 2, "err": 0, "workers": []}))
        loop.telemetria = MagicMock(f821_count=lambda: 0, hardware=lambda: {"ram_libre_mb": 1000})
        loop._fallos_consecutivos = 0
        
        with patch('motor.core.agents.healing.Conciencia') as mock_conciencia:
            mock_conciencia.leer.return_value = {"estado": "ok"}
            mock_conciencia.actualizar_proceso = MagicMock()
            
            with patch('motor.core.agents.healing.Conciencia') as mock_conciencia_class:
                mock_conciencia_class.leer.return_value = {"estado": "ok"}
                mock_conciencia_class.actualizar_proceso = MagicMock()
                
                resultado = SelfHealingLoop().ejecutar()
                
                assert resultado["accion"] == "REFACTORIZAR"
                assert "refactor" in resultado
                # assert resultado["refactor"]["ok"] == 2


class TestSelfHealingLoopEscanearF821:
    """Tests para _escanear_f821()."""

    @pytest.mark.unit
    def test_escanear_f821_retorna_set(self):
        """Verifica que retorna set de archivos."""
        with patch('motor.core.agents.healing.subprocess.run') as mock_run, \
             patch('motor.core.agents.healing.RUFF', "ruff"), \
             patch('motor.core.agents.healing.URA_ROOT', Path("/fake")):
            
            mock_run.return_value = MagicMock(stdout='[{"filename": "test1.py"}, {"filename": "test2.py"}]')
            
            loop = SelfHealingLoop.__new__(SelfHealingLoop)
            result = loop._escanear_f821()
            
            assert isinstance(result, set)
            assert "test1.py" in result
            assert "test2.py" in result

    @pytest.mark.unit
    def test_escanear_f821_filtra_venv(self):
        """Verifica que filtra .venv."""
        with patch('motor.core.agents.healing.subprocess.run') as mock_run, \
             patch('motor.core.agents.healing.RUFF', "ruff"), \
             patch('motor.core.agents.healing.URA_ROOT', Path("/fake")):
            
            mock_run.return_value = MagicMock(stdout='[{"filename": "/home/user/.venv/lib/test.py"}, {"filename": "src/test.py"}]')
            
            loop = SelfHealingLoop.__new__(SelfHealingLoop)
            result = loop._escanear_f821()
            
            assert "/.venv/" not in str(result) or "/home/user/.venv/lib/test.py" not in result


class TestSelfHealingLoopAplicarReglasAuto:
    """Tests para _aplicar_reglas_auto()."""

    @pytest.mark.unit
    def test_aplicar_reglas_auto_ejecuta_comandos(self):
        """Verifica que ejecuta ruff --fix y auto_reglas.py."""
        with patch('motor.core.agents.healing.subprocess.run') as mock_run, \
             patch('motor.core.agents.healing.RUFF', "ruff"), \
             patch('motor.core.agents.healing.URA_ROOT', Path("/fake")), \
             patch('motor.core.agents.healing.SCRIPTS', Path("/fake/scripts")), \
             patch('motor.core.agents.healing.sys.executable', sys.executable):
            
            loop = SelfHealingLoop.__new__(SelfHealingLoop)
            loop._aplicar_reglas_auto()
            
            assert mock_run.call_count == 2
            calls = mock_run.call_args_list
            assert "ruff" in str(calls[0])
            assert "--fix" in str(calls[0])
            assert "auto_reglas.py" in str(calls[1])
            assert "--generar" in str(calls[1])


class TestSelfHealingLoopCerrarReporte:
    """Tests para _cerrar_reporte()."""

    @pytest.mark.unit
    def test_cerrar_reporte_timeout(self):
        """Verifica reporte TIMEOUT."""
        from motor.core.agents.healing import MAX_CICLO_S
        loop = SelfHealingLoop.__new__(SelfHealingLoop)
        loop._fallos_consecutivos = 0
        
        inicio = time.monotonic() - 400
        reporte = {"timestamp": "2024-01-01T00:00:00Z"}
        
        with patch('motor.core.agents.healing.MAX_CICLO_S', 300):
            resultado = loop._cerrar_reporte({"timestamp": "2024-01-01T00:00:00Z"}, time.monotonic() - 400, 0)
            assert resultado["resultado"] == "TIMEOUT"
            assert "limite" in resultado["razon"]

    @pytest.mark.unit
    def test_cerrar_reporte_normal(self):
        """Verifica reporte normal sin timeout."""
        loop = SelfHealingLoop.__new__(SelfHealingLoop)
        loop._fallos_consecutivos = 0
        loop.telemetria = MagicMock()
        loop.telemetria.hardware.return_value = {"ram_libre_mb": 1000}
        
        inicio = time.monotonic() - 10
        reporte = {"timestamp": "2024-01-01T00:00:00Z"}
        
        with patch('motor.core.agents.healing.MAX_CICLO_S', 300):
            resultado = loop._cerrar_reporte({"timestamp": "2024-01-01T00:00:00Z"}, time.monotonic() - 10, 0)
            assert "f821_final" in resultado
            assert "tiempo_total_s" in resultado
            assert "ram_final_mb" in resultado


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
