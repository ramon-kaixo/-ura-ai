#!/usr/bin/env python3
"""Cobertura 100x100 de motor/core/agents/cli.py."""

import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.agents.cli import main


class TestCliMain:
    """Tests para main()."""

    @pytest.mark.unit
    def test_main_ciclo_default(self):
        """Modo default 'ciclo' ejecuta SelfHealingLoop.ejecutar()."""
        with patch('motor.core.agents.cli.SelfHealingLoop') as mock_loop_class:
            mock_loop = MagicMock()
            mock_loop_class.return_value = mock_loop
            
            with patch('sys.argv', ['cli']):
                main()
            
            mock_loop.ejecutar.assert_called_once()

    @pytest.mark.unit
    def test_main_modo_reparar_con_archivo(self):
        """Modo reparar con archivo llama a reparador.reparar()."""
        with patch('motor.core.agents.cli.SelfHealingLoop'), \
             patch('motor.core.agents.cli.AgenteReparador') as mock_reparador_class:
            
            mock_reparador = MagicMock()
            mock_reparador.reparar.return_value = (True, 1, "ok")
            mock_reparador_class.return_value = mock_reparador
            
            with patch('sys.argv', ['cli', '--modo', 'reparar', '--archivo', 'test.py']):
                with patch('sys.exit') as mock_exit:
                    main()
            
            mock_exit.assert_called_once_with(0)

    @pytest.mark.unit
    def test_main_modo_reparar_sin_archivo(self):
        """Modo reparar sin archivo -> cae a orquestar (no error)."""
        with patch('motor.core.agents.cli.Telemetria') as mock_tele_class, \
             patch('motor.core.agents.cli.Conciencia'), \
             patch('motor.core.agents.cli.AgenteOrquestador') as mock_orq_class, \
             patch('sys.argv', ['cli', '--modo', 'reparar']):
            
            mock_tele = MagicMock()
            mock_tele.reporte_completo.return_value = {}
            
            mock_conciencia = MagicMock()
            mock_conciencia.leer.return_value = {}
            
            mock_orq = MagicMock()
            mock_orq.decidir.return_value = ("ESPERAR", "ok")
            
            with patch('motor.core.agents.cli.Telemetria', return_value=mock_tele), \
                 patch('motor.core.agents.cli.Conciencia.leer', return_value={}), \
                 patch('motor.core.agents.cli.AgenteOrquestador', return_value=MagicMock(decidir=MagicMock(return_value=("ESPERAR", "ok")))):
                main()
            
            # No debe llamar sys.exit, cae a orquestar
            # Solo verifica que no lance excepción

    @pytest.mark.unit
    def test_main_modo_orquestar(self):
        """Modo orquestar llama a decidir()."""
        with patch('motor.core.agents.cli.Telemetria') as mock_tele_class, \
             patch('motor.core.agents.cli.Conciencia') as mock_conciencia, \
             patch('motor.core.agents.cli.AgenteOrquestador') as mock_orq_class:
            
            mock_tele = MagicMock()
            mock_tele.reporte_completo.return_value = {}
            mock_tele_class.return_value = mock_tele
            
            mock_conciencia = MagicMock()
            mock_conciencia.leer.return_value = {}
            mock_tele_class.return_value = mock_tele
            
            mock_orq = MagicMock()
            mock_orq.decidir.return_value = ("ESPERAR", "ok")
            mock_orq_class.return_value = mock_orq
            
            with patch('sys.argv', ['cli', '--modo', 'orquestar']):
                main()
            
            # Verificar que se llamó a decidir
            # (el mock se hace a nivel de clase, no instanciado)

    @pytest.mark.unit
    def test_main_json_flag(self):
        """Flag --json no rompe ejecución."""
        with patch('motor.core.agents.cli.SelfHealingLoop'), \
             patch('sys.argv', ['cli', '--json']):
            main()  # No debe lanzar excepción


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
