"""Tests for core/agents/ejecutor.py."""

from unittest.mock import MagicMock, patch
import pytest
from core.agents.ejecutor import AgenteEjecutor

class TestEjecutar:
    @patch("core.agents.ejecutor.subprocess.Popen")
    @patch("core.agents.ejecutor.threading.Timer")
    @patch("core.config_manager.get_ollama_url", return_value="http://localhost:11434")
    def test_ejecutar_ok(self, mock_ollama, mock_timer, mock_popen):
        mock_proc = MagicMock()
        ok = chr(0x2705) + " OK"
        mock_proc.communicate.return_value = (ok + "\n" + ok + "\n", None)
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc
        ej = AgenteEjecutor()
        result = ej.ejecutar(workers=1, timeout=10)
        assert result["ok"] == 2
        assert result["err"] == 0
        assert len(result["workers"]) == 1
        assert result["workers"][0]["ok"] == 2

    @patch("core.agents.ejecutor.subprocess.Popen")
    @patch("core.agents.ejecutor.threading.Timer")
    @patch("core.config_manager.get_ollama_url", return_value="http://localhost:11434")
    def test_ejecutar_error(self, mock_ollama, mock_timer, mock_popen):
        mock_proc = MagicMock()
        ok = chr(0x2705) + " OK"
        err = chr(0x274c) + " Error"
        mock_proc.communicate.return_value = (err + "\n" + ok + "\n", None)
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc
        ej = AgenteEjecutor()
        result = ej.ejecutar(workers=1, timeout=10)
        assert result["ok"] == 1
        assert result["err"] == 1

    @patch("core.agents.ejecutor.subprocess.Popen")
    @patch("core.agents.ejecutor.threading.Timer")
    @patch("core.config_manager.get_ollama_url", return_value="http://localhost:11434")
    def test_ejecutar_multiple_workers(self, mock_ollama, mock_timer, mock_popen):
        mock_proc = MagicMock()
        ok = chr(0x2705) + " OK"
        mock_proc.communicate.return_value = (ok + "\n", None)
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc
        ej = AgenteEjecutor()
        result = ej.ejecutar(workers=3, timeout=10)
        assert len(result["workers"]) == 3

    def test_modelo_configurado(self):
        ej = AgenteEjecutor()
        assert ej.MODELO == "deepseek-coder:6.7b"
