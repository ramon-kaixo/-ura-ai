"""Tests for core/agents/reparador.py."""

from unittest.mock import MagicMock, patch

from motor.core.agents.reparador import AgenteReparador


class TestReparar:
    def test_archivo_no_existe(self):
        rep = AgenteReparador()
        ok, nivel, msg = rep.reparar("/tmp/no_existe.py", [])
        assert ok is False
        assert nivel == -1
        assert "no encontrado" in msg

    @patch("motor.core.agents.reparador.shutil.copy2")
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

    @patch("motor.core.agents.reparador.shutil.copy2")
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

    @patch("motor.core.agents.reparador.shutil.copy2")
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

    @patch("motor.core.agents.reparador.shutil.copy2")
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


class TestNiveles:
    def test_nivel_1_exito(self, tmp_path):
        f = tmp_path / "ok.py"
        f.write_text("x = 1")
        rep = AgenteReparador()
        with patch("motor.core.agents.reparador.subprocess.run", return_value=MagicMock()):
            assert rep._nivel_1(f) is True

    def test_nivel_1_compilation_error(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("x = 1")
        rep = AgenteReparador()
        with patch("motor.core.agents.reparador.subprocess.run", return_value=MagicMock()), patch("builtins.compile", side_effect=SyntaxError("boom")):
                assert rep._nivel_1(f) is False

    def test_nivel_2_sin_errores(self, tmp_path):
        f = tmp_path / "ok.py"
        f.write_text("x = 1")
        rep = AgenteReparador()
        r = MagicMock()
        r.returncode = 0
        with patch("motor.core.agents.reparador.subprocess.run", return_value=r):
            assert rep._nivel_2(f, "modelo") is True

    def test_nivel_2_genera_fix(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("missing = valor_no_definido")
        rep = AgenteReparador(llm=MagicMock())
        rep._llm.generate.return_value = "```python\nx = 1\n```"
        r = MagicMock()
        r.returncode = 1
        r.stderr = "F821: undefined name 'valor_no_definido'"
        r.stdout = ""
        with patch("motor.core.agents.reparador.subprocess.run", return_value=r):
            assert rep._nivel_2(f, "modelo") is True
        assert "x = 1" in f.read_text()

    def test_nivel_3_exito(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("y = indefinido")
        rep = AgenteReparador()
        r = MagicMock()
        r.returncode = 1
        r.stderr = "F821: undefined name 'indefinido'"
        cm = MagicMock()
        cm.read.return_value = b'{"choices": [{"message": {"content": "```python\\nz = 1\\n```"}}]}'
        with patch("motor.core.agents.reparador.subprocess.run", return_value=r), patch("urllib.request.urlopen", return_value=cm) as mock_url:
                mock_url.return_value.__enter__.return_value = cm
                assert rep._nivel_3(f) is True
        assert "z = 1" in f.read_text()

    def test_nivel_3_urlopen_error(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("y = indefinido")
        rep = AgenteReparador()
        r = MagicMock()
        r.returncode = 1
        r.stderr = "F821"
        with patch("motor.core.agents.reparador.subprocess.run", return_value=r), patch("urllib.request.urlopen", side_effect=OSError("conn")):
                assert rep._nivel_3(f) is False
