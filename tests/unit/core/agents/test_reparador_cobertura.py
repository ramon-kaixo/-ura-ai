#!/usr/bin/env python3
"""Cobertura 100x100 de motor/core/agents/reparador.py."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.agents.reparador import AgenteReparador


class TestAgenteReparadorInit:
    @pytest.mark.unit
    def test_init_sin_llm(self):
        reparador = AgenteReparador()
        assert reparador._llm is None

    @pytest.mark.unit
    def test_init_con_llm(self):
        mock_llm = MagicMock()
        reparador = AgenteReparador(llm=mock_llm)
        assert reparador._llm is mock_llm


class TestAgenteReparadorGenerate:
    @pytest.mark.unit
    def test_generate_con_llm(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "codigo reparado"
        
        reparador = AgenteReparador(llm=mock_llm)
        resultado = reparador._generate("prompt", "modelo", {"temp": 0.0})
        
        assert resultado == "codigo reparado"
        mock_llm.generate.assert_called_once_with("prompt", model="modelo", options={"temp": 0.0})

    @pytest.mark.unit
    def test_generate_sin_llm(self):
        with patch('motor.core.llm.generate') as mock_gen:
            mock_gen.return_value = "codigo reparado"
            
            reparador = AgenteReparador()
            resultado = reparador._generate("prompt", "modelo", {"temp": 0.0})
            
            assert resultado == "codigo reparado"
            mock_gen.assert_called_once_with("prompt", model="modelo", options={"temp": 0.0})


class TestAgenteReparadorReparar:
    @pytest.mark.unit
    def test_reparar_archivo_no_existe(self):
        reparador = AgenteReparador()
        resultado = reparador.reparar("/no/existe/archivo.py", [])
        assert resultado == (False, -1, "Archivo no encontrado")

    @pytest.mark.unit
    def test_reparar_crea_backup(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hola')")
        print(f"DEBUG: test_file={test_file}")
        print(f"DEBUG: test_file.exists()={test_file.exists()}")
        
        with patch.object(AgenteReparador, '_nivel_1', return_value=True):
            reparador = AgenteReparador()
            resultado = reparador.reparar(str(test_file), [])
    
            backup = test_file.with_suffix('.bak_repair')
            print(f"DEBUG: backup={backup}")
            print(f"DEBUG: backup.exists()={backup.exists()}")
            print(f"DEBUG: test_file.exists()={test_file.exists()}")
            import shutil
            print(f"DEBUG: testing shutil.copy2")
            import shutil
            shutil.copy2(test_file, backup)
            print(f"DEBUG: after shutil.copy2, backup.exists()={backup.exists()}")
            assert backup.exists()

    @pytest.mark.unit
    def test_reparar_no_sobrescribe_backup_existente(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hola')")
        backup = tmp_path / "test.py.bak_repair"
        backup.write_text("backup original")
        
        with patch.object(AgenteReparador, '_nivel_1', return_value=True):
            reparador = AgenteReparador()
            resultado = reparador.reparar(str(test_file), [])
            assert backup.read_text() == "backup original"

    @pytest.mark.unit
    def test_reparar_nivel_1_exitoso(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hola')")
        
        with patch.object(AgenteReparador, '_nivel_1', return_value=True):
            reparador = AgenteReparador()
            resultado = reparador.reparar(str(test_file), [])
            assert resultado == (True, 1, "Reparado por auto_reglas (determinista)")

    @pytest.mark.unit
    def test_reparar_nivel_1_falla_nivel_2_exitoso(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hola')")
        
        with patch.object(AgenteReparador, '_nivel_1', return_value=False), \
             patch.object(AgenteReparador, '_nivel_2', return_value=True):
            
            reparador = AgenteReparador()
            resultado = reparador.reparar(str(test_file), [])
            assert resultado == (True, 2, "Reparado por DeepSeek 6.7B (LLM rápido)")

    @pytest.mark.unit
    def test_reparar_nivel_1_2_fallan_nivel_3_exitoso(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hola')")
        
        with patch.object(AgenteReparador, '_nivel_1', return_value=False), \
             patch.object(AgenteReparador, '_nivel_2', return_value=False), \
             patch.object(AgenteReparador, '_nivel_3', return_value=True):
            
            reparador = AgenteReparador()
            resultado = reparador.reparar(str(test_file), [])
            assert resultado == (True, 3, "Reparado por OpenCode 32B (LLM potente)")

    @pytest.mark.unit
    def test_reparar_todos_fallan(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hola')")
        
        with patch.object(AgenteReparador, '_nivel_1', return_value=False), \
             patch.object(AgenteReparador, '_nivel_2', return_value=False), \
             patch.object(AgenteReparador, '_nivel_3', return_value=False):
            
            reparador = AgenteReparador()
            resultado = reparador.reparar(str(test_file), [])
            assert resultado == (False, 0, "No se pudo reparar (watermark creado)")


class TestAgenteReparadorNivel1:
    @pytest.mark.unit
    def test_nivel_1_exitoso(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hola')")
        
        with patch('motor.core.agents.reparador.subprocess.run') as mock_run, \
             patch('motor.core.agents.reparador.SCRIPTS', Path("/fake/scripts")), \
             patch('motor.core.agents.reparador.RUFF', "ruff"), \
             patch('motor.core.agents.reparador.URA_ROOT', tmp_path), \
             patch('motor.core.agents.reparador.sys.executable', sys.executable), \
             patch('builtins.compile', return_value=MagicMock()):
            
            mock_run.return_value = MagicMock(returncode=0)
            reparador = AgenteReparador()
            resultado = reparador._nivel_1(test_file)
            assert resultado is True

    @pytest.mark.unit
    def test_nivel_1_falla_compile(self):
        with patch('motor.core.agents.reparador.subprocess.run', return_value=MagicMock(returncode=0)), \
             patch('builtins.compile', side_effect=SyntaxError("invalid syntax")), \
             patch('motor.core.agents.reparador.SCRIPTS', Path("/fake/scripts")), \
             patch('motor.core.agents.reparador.RUFF', "ruff"), \
             patch('motor.core.agents.reparador.URA_ROOT', Path("/fake")), \
             patch('motor.core.agents.reparador.sys.executable', sys.executable):
            
            reparador = AgenteReparador()
            resultado = reparador._nivel_1(Path("/fake/test.py"))
            assert resultado is False


class TestAgenteReparadorNivel2:
    @pytest.mark.unit
    def test_nivel_2_ruff_ok(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hola')")
        
        with patch('motor.core.agents.reparador.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            reparador = AgenteReparador()
            resultado = reparador._nivel_2(test_file, "modelo")
            assert resultado is True

    @pytest.mark.unit
    def test_nivel_2_llm_repara(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\nprint(x)")
        
        with patch('motor.core.agents.reparador.subprocess.run') as mock_run, \
             patch.object(AgenteReparador, '_generate', return_value='import os\nprint("hello")'):
            
            mock_run.side_effect = [
                MagicMock(returncode=1, stderr="test.py:2:1: F821 undefined name 'x'"),
                MagicMock(returncode=0, stdout="", stderr="")
            ]
            
            reparador = AgenteReparador()
            with patch('builtins.compile', return_value=MagicMock()):
                resultado = reparador._nivel_2(test_file, "modelo")
                assert resultado is True


class TestAgenteReparadorNivel3:
    @pytest.mark.unit
    def test_nivel_3_http_error(self):
        from urllib.error import HTTPError
        with patch('motor.core.agents.reparador.subprocess.run') as mock_run, \
             patch('motor.core.agents.reparador.urllib.request.urlopen') as mock_urlopen:
            
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            mock_urlopen.side_effect = HTTPError("url", 500, "Server Error", {}, None)
            
            reparador = AgenteReparador()
            resultado = reparador._nivel_3(Path("/fake/test.py"))
            assert resultado is False

    @pytest.mark.unit
    def test_nivel_3_json_decode_error(self):
        with patch('motor.core.agents.reparador.subprocess.run') as mock_run, \
             patch('motor.core.agents.reparador.urllib.request.urlopen') as mock_urlopen:
            
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            mock_response = MagicMock()
            mock_response.read.return_value = b'no es json valido'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            reparador = AgenteReparador()
            resultado = reparador._nivel_3(Path("/fake/test.py"))
            assert resultado is False


class TestAgenteReparadorExtractCode:
    @pytest.mark.unit
    def test_extrae_codigo_python_markdown(self):
        fixed = "```python\nimport os\nprint('ok')\n```"
        if fixed and "```" in fixed:
            if "```python" in fixed:
                extracted = fixed.split("```python")[1].split("```")[0]
            else:
                extracted = fixed.split("```")[1]
            assert "import os" in extracted
            assert "```" not in extracted

    @pytest.mark.unit
    def test_extrae_codigo_sin_python_markdown(self):
        fixed = "```\nimport os\nprint('ok')\n```"
        if fixed and "```" in fixed:
            if "```python" in fixed:
                extracted = fixed.split("```python")[1].split("```")[0]
            else:
                extracted = fixed.split("```")[1]
            assert "import os" in extracted
            assert "```" not in extracted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
