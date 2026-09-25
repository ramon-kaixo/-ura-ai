#!/usr/bin/env python3
"""Cobertura 100x100 de motor/core/agents/ejecutor.py."""

import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.agents.ejecutor import AgenteEjecutor


class TestAgenteEjecutorInit:
    """Tests para inicialización."""

    @pytest.mark.unit
    def test_modelo_default(self):
        """Verifica modelo por defecto."""
        agente = AgenteEjecutor()
        assert agente.MODELO == "qwen3-coder:30b"


class TestAgenteEjecutorEjecutar:
    """Tests para método ejecutar()."""

    @pytest.mark.unit
    def test_ejecutar_default_params(self):
        """Verifica parámetros por defecto."""
        with patch('motor.core.agents.ejecutor.subprocess.Popen') as mock_popen, \
             patch('motor.core.agents.ejecutor.threading.Timer') as mock_timer, \
             patch('motor.core.config_manager.get_ollama_url', return_value="http://localhost:11434"), \
             patch('motor.core.agents.ejecutor.URA_ROOT', Path("/fake/ura")):
            
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ("✅ OK 1\n✅ OK 2\n", "")
            mock_proc.poll.return_value = 0
            mock_popen.return_value = mock_proc
            
            mock_timer_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance
            
            agente = AgenteEjecutor()
            resultado = agente.ejecutar(workers=2, timeout=10)
            
            assert "ok" in resultado
            assert "err" in resultado
            assert "workers" in resultado
            assert len(resultado["workers"]) == 2

    @pytest.mark.unit
    def test_ejecutar_workers_personalizado(self):
        """Verifica workers personalizado."""
        with patch('motor.core.agents.ejecutor.subprocess.Popen') as mock_popen, \
             patch('motor.core.agents.ejecutor.threading.Timer'), \
             patch('motor.core.config_manager.get_ollama_url', return_value="http://localhost:11434"), \
             patch('motor.core.agents.ejecutor.URA_ROOT', Path("/fake/ura")):
            
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ("", "")
            mock_proc.poll.return_value = 0
            mock_popen.return_value = mock_proc
            
            agente = AgenteEjecutor()
            resultado = agente.ejecutar(workers=1, timeout=5)
            
            assert len(resultado["workers"]) == 1

    @pytest.mark.unit
    def test_ejecutar_env_vars_correctas(self):
        """Verifica variables de entorno configuradas."""
        with patch('motor.core.agents.ejecutor.subprocess.Popen') as mock_popen, \
             patch('motor.core.agents.ejecutor.threading.Timer'), \
             patch('motor.core.config_manager.get_ollama_url', return_value="http://localhost:11434"), \
             patch('motor.core.agents.ejecutor.URA_ROOT', Path("/fake/ura")):
            
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ("", "")
            mock_proc.poll.return_value = 0
            mock_popen.return_value = mock_proc
            
            agente = AgenteEjecutor()
            agente.ejecutar(workers=1, timeout=5)
            
            call_args = mock_popen.call_args
            env = call_args[1]['env']
            assert "REFACTOR_WORKER_ID" in env
            assert "REFACTOR_WORKER_TOTAL" in env
            assert "REFACTOR_MODEL" in env
            assert "REFACTOR_MODEL_FALLBACK" in env
            assert "MIN_LINES" in env
            assert "OLLAMA_URL" in env
            assert "URA_ROOT" in env

    @pytest.mark.unit
    def test_ejecutar_timeout_expired(self):
        """Verifica manejo de timeout."""
        import subprocess
        with patch('motor.core.agents.ejecutor.subprocess.Popen') as mock_popen, \
             patch('motor.core.agents.ejecutor.threading.Timer'), \
             patch('motor.core.config_manager.get_ollama_url', return_value="http://localhost:11434"), \
             patch('motor.core.agents.ejecutor.URA_ROOT', Path("/fake/ura")), \
             patch('motor.core.agents.ejecutor.log'):
            
            mock_proc = MagicMock()
            mock_proc.communicate.side_effect = subprocess.TimeoutExpired("cmd", 10)
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc
            
            agente = AgenteEjecutor()
            resultado = agente.ejecutar(workers=1, timeout=1)
            
            assert resultado["workers"][0]["timeout"] is True
            assert resultado["workers"][0]["err"] == 1

    @pytest.mark.unit
    def test_ejecutar_cuenta_ok_err(self):
        """Verifica conteo de OK y Error."""
        with patch('motor.core.agents.ejecutor.subprocess.Popen') as mock_popen, \
             patch('motor.core.agents.ejecutor.threading.Timer'), \
             patch('motor.core.config_manager.get_ollama_url', return_value="http://localhost:11434"), \
             patch('motor.core.agents.ejecutor.URA_ROOT', Path("/fake/ura")):
            
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ("✅ OK\n✅ OK\n❌ Error\n", "")
            mock_proc.poll.return_value = 0
            mock_popen.return_value = mock_proc
            
            agente = AgenteEjecutor()
            resultado = agente.ejecutar(workers=1, timeout=10)
            
            assert resultado["ok"] == 2
            assert resultado["err"] == 1


class TestAgenteEjecutorEdgeCases:
    """Casos edge."""

    @pytest.mark.unit
    def test_ejecutar_workers_cero(self):
        """Verifica workers=0."""
        agente = AgenteEjecutor()
        resultado = agente.ejecutar(workers=0, timeout=10)
        
        assert resultado["ok"] == 0
        assert resultado["err"] == 0
        assert resultado["workers"] == []

    @pytest.mark.unit
    def test_ejecutar_proceso_ya_terminado(self):
        """Proceso ya terminado antes de communicate."""
        with patch('motor.core.agents.ejecutor.subprocess.Popen') as mock_popen, \
             patch('motor.core.agents.ejecutor.threading.Timer'), \
             patch('motor.core.config_manager.get_ollama_url', return_value="http://localhost:11434"), \
             patch('motor.core.agents.ejecutor.URA_ROOT', Path("/fake/ura")):
            
            mock_proc = MagicMock()
            mock_proc.poll.return_value = 0
            mock_proc.communicate.return_value = ("", "")
            mock_popen.return_value = mock_proc
            
            agente = AgenteEjecutor()
            resultado = agente.ejecutar(workers=1, timeout=10)
            
            assert "workers" in resultado


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
