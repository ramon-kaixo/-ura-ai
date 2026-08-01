"""Tests for core/agents/reparador.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.agents.reparador import AgenteReparador


class TestReparar:
    def test_archivo_no_existe(self):
        rep = AgenteReparador()
        ok, nivel, msg = rep.reparar("/tmp/no_existe.py", [])
        assert ok is False
        assert nivel == -1
        assert "no encontrado" in msg

    @patch("core.agents.reparador.shutil.copy2")
    @patch.object(AgenteReparador, "_nivel_1", return_value=True)
    def test_nivel_1_ok(self, mock_n1, mock_copy, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        rep = AgenteReparador()
        ok, nivel, msg = rep.reparar(str(f), [])
        assert ok is True
        assert nivel == 1
        assert "determinista" in msg
        mock_n1.assert_called_once()

    @patch("core.agents.reparador.shutil.copy2")
    @patch.object(AgenteReparador, "_nivel_1", return_value=False)
    @patch.object(AgenteReparador, "_nivel_2", return_value=True)
    def test_nivel_2_ok(self, mock_n2, mock_n1, mock_copy, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        rep = AgenteReparador()
        ok, nivel, msg = rep.reparar(str(f), [])
        assert ok is True
        assert nivel == 2
        assert "DeepSeek" in msg

    @patch("core.agents.reparador.shutil.copy2")
    @patch.object(AgenteReparador, "_nivel_1", return_value=False)
    @patch.object(AgenteReparador, "_nivel_2", return_value=False)
    @patch.object(AgenteReparador, "_nivel_3", return_value=True)
    def test_nivel_3_ok(self, mock_n3, mock_n2, mock_n1, mock_copy, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        rep = AgenteReparador()
        ok, nivel, msg = rep.reparar(str(f), [])
        assert ok is True
        assert nivel == 3
        assert "OpenCode" in msg

    @patch("core.agents.reparador.shutil.copy2")
    @patch.object(AgenteReparador, "_nivel_1", return_value=False)
    @patch.object(AgenteReparador, "_nivel_2", return_value=False)
    @patch.object(AgenteReparador, "_nivel_3", return_value=False)
    def test_todos_fallan(self, mock_n3, mock_n2, mock_n1, mock_copy, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        rep = AgenteReparador()
        ok, nivel, msg = rep.reparar(str(f), [])
        assert ok is False
        assert nivel == 0
        assert "No se pudo" in msg

    def test_backup_creado(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        rep = AgenteReparador()
        with patch.object(rep, "_nivel_1", return_value=True):
            rep.reparar(str(f), [])
        assert (tmp_path / "test.bak_repair").exists()


class TestGenerate:
    def test_con_llm_inyectado(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "fixed code"
        rep = AgenteReparador(llm=mock_llm)
        result = rep._generate("prompt", "model")
        assert result == "fixed code"
        mock_llm.generate.assert_called_once_with("prompt", model="model", options=None)

    @patch("motor.core.llm.generate")
    def test_fallback_a_motor(self, mock_gen):
        mock_gen.return_value = "motor code"
        rep = AgenteReparador(llm=None)
        result = rep._generate("prompt", "model")
        assert result == "motor code"
        mock_gen.assert_called_once_with("prompt", model="model", options=None)
