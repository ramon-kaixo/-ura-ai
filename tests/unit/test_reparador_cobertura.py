"""Cobertura 100% de motor.core.agents.reparador (AgenteReparador) — paths directos de _nivel_1/_nivel_2/_nivel_3."""

import json
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

from motor.core.agents.reparador import AgenteReparador


def _run_result(returncode: int, stderr: str = "", stdout: str = "") -> MagicMock:
    return MagicMock(returncode=returncode, stderr=stderr, stdout=stdout)


class TestRepararCaminos:
    def test_archivo_inexistente_devuelve_error(self) -> None:
        ok, nivel, msg = AgenteReparador().reparar("/tmp/ura_inexistente_xyz.py", [])
        assert (ok, nivel) == (False, -1)
        assert "no encontrado" in msg

    def test_ruta_inexistente_como_path(self) -> None:
        ok, nivel, _ = AgenteReparador().reparar(Path("/tmp/ura_inexistente_xyz.py"), [])
        assert (ok, nivel) == (False, -1)

    def test_acepta_path_directo(self, tmp_path) -> None:
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        rep = AgenteReparador()
        with patch.object(AgenteReparador, "_nivel_1", return_value=True):
            ok, nivel, msg = rep.reparar(f, [])
        assert (ok, nivel) == (True, 1)
        assert "determinista" in msg

    def test_backup_existente_no_se_copia(self, tmp_path) -> None:
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        (tmp_path / "a.bak_repair").write_text("x = 0\n")
        rep = AgenteReparador()
        with (
            patch("motor.core.agents.reparador.shutil.copy2") as mock_copy,
            patch.object(AgenteReparador, "_nivel_1", return_value=True),
        ):
            rep.reparar(str(f), [])
        mock_copy.assert_not_called()

    def test_nivel_2_devuelve_mensaje_deepseek(self, tmp_path) -> None:
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        rep = AgenteReparador()
        with (
            patch.object(AgenteReparador, "_nivel_1", return_value=False),
            patch.object(AgenteReparador, "_nivel_2", return_value=True),
        ):
            ok, nivel, msg = rep.reparar(str(f), [])
        assert (ok, nivel) == (True, 2)
        assert "DeepSeek" in msg

    def test_nivel_3_devuelve_mensaje_opencode(self, tmp_path) -> None:
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        rep = AgenteReparador()
        with (
            patch.object(AgenteReparador, "_nivel_1", return_value=False),
            patch.object(AgenteReparador, "_nivel_2", return_value=False),
            patch.object(AgenteReparador, "_nivel_3", return_value=True),
        ):
            ok, nivel, msg = rep.reparar(str(f), [])
        assert (ok, nivel) == (True, 3)
        assert "OpenCode" in msg

    def test_todos_los_niveles_fallan(self, tmp_path) -> None:
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        rep = AgenteReparador()
        with (
            patch.object(AgenteReparador, "_nivel_1", return_value=False),
            patch.object(AgenteReparador, "_nivel_2", return_value=False),
            patch.object(AgenteReparador, "_nivel_3", return_value=False),
        ):
            ok, nivel, msg = rep.reparar(str(f), [])
        assert (ok, nivel) == (False, 0)
        assert "No se pudo" in msg


class TestGenerar:
    def test_usa_llm_inyectado(self) -> None:
        llm = MagicMock()
        llm.generate.return_value = "fixed"
        result = AgenteReparador(llm=llm)._generate("p", "m", {"t": 0})
        assert result == "fixed"
        llm.generate.assert_called_once_with("p", model="m", options={"t": 0})

    def test_cae_al_generate_de_motor(self) -> None:
        with patch("motor.core.llm.generate", return_value="motor") as mock_gen:
            result = AgenteReparador()._generate("p", "m")
        assert result == "motor"
        mock_gen.assert_called_once_with("p", model="m", options=None)


class TestNivel1:
    def test_arregla_con_las_tres_pasadas(self, tmp_path) -> None:
        f = tmp_path / "rotos.py"
        f.write_text("x = 1\n")
        rep = AgenteReparador()
        with patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(0)) as mock_run:
            assert rep._nivel_1(f) is True
        assert mock_run.call_count == 3

    def test_syntax_error_tras_pasadas_devuelve_false(self, tmp_path) -> None:
        f = tmp_path / "rotos.py"
        f.write_text("x =\n")
        rep = AgenteReparador()
        with patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(0)):
            assert rep._nivel_1(f) is False

    def test_timeout_devuelve_false(self, tmp_path) -> None:
        f = tmp_path / "rotos.py"
        f.write_text("x = 1\n")
        rep = AgenteReparador()
        with patch(
            "motor.core.agents.reparador.subprocess.run",
            side_effect=TimeoutExpired("cmd", 15),
        ):
            assert rep._nivel_1(f) is False


class TestNivel2:
    def test_sin_errores_f821_no_llama_al_llm(self, tmp_path) -> None:
        f = tmp_path / "ok.py"
        f.write_text("x = 1\n")
        llm = MagicMock()
        rep = AgenteReparador(llm=llm)
        with patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(0)):
            assert rep._nivel_2(f, "modelo") is True
        llm.generate.assert_not_called()

    def test_repara_con_fences_markdown_python(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        llm = MagicMock()
        llm.generate.return_value = "```python\nx = 1\n```"
        rep = AgenteReparador(llm=llm)
        with patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(1, stderr="F821: undefined name 'x'")):
            assert rep._nivel_2(f, "modelo") is True
        assert f.read_text() == "\nx = 1\n"
        llm.generate.assert_called_once()

    def test_repara_con_fences_genericos(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        llm = MagicMock()
        llm.generate.return_value = "```\nx = 2\n```"
        rep = AgenteReparador(llm=llm)
        with patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(1, stderr="F821")):
            assert rep._nivel_2(f, "modelo") is True
        assert f.read_text() == "\nx = 2\n"

    def test_errores_leo_de_stdout_cuando_stderr_vacio(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        llm = MagicMock()
        llm.generate.return_value = "x = 1"
        rep = AgenteReparador(llm=llm)
        with patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(1, stdout="F821 en stdout")):
            assert rep._nivel_2(f, "modelo") is True

    def test_sin_fences_escribe_tal_cual(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        llm = MagicMock()
        llm.generate.return_value = "x = 3"
        rep = AgenteReparador(llm=llm)
        with patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(1, stderr="F821")):
            assert rep._nivel_2(f, "modelo") is True
        assert f.read_text() == "x = 3"

    def test_respuesta_vacia_compila_vacio(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        llm = MagicMock()
        llm.generate.return_value = ""
        rep = AgenteReparador(llm=llm)
        with patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(1, stderr="F821")):
            assert rep._nivel_2(f, "modelo") is True
        assert f.read_text() == ""

    def test_error_del_llm_devuelve_false(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("ollama caida")
        rep = AgenteReparador(llm=llm)
        with patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(1, stderr="F821")):
            assert rep._nivel_2(f, "modelo") is False


class TestNivel3:
    def _responde(self, fixed: str) -> MagicMock:
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.read.return_value = json.dumps({"choices": [{"message": {"content": fixed}}]}).encode()
        return resp

    def test_repara_con_llm_potente(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        resp = self._responde("```python\nx = 4\n```")
        rep = AgenteReparador()
        with (
            patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(1, stderr="F821")),
            patch("motor.core.agents.reparador.urllib.request.urlopen", return_value=resp),
        ):
            assert rep._nivel_3(f) is True
        assert f.read_text() == "\nx = 4\n"

    def test_repara_con_fences_genericos(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        resp = self._responde("```\nx = 5\n```")
        rep = AgenteReparador()
        with (
            patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(1, stderr="F821")),
            patch("motor.core.agents.reparador.urllib.request.urlopen", return_value=resp),
        ):
            assert rep._nivel_3(f) is True
        assert f.read_text() == "\nx = 5\n"

    def test_sin_fences_escribe_tal_cual(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        resp = self._responde("x = 6")
        rep = AgenteReparador()
        with (
            patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(0)),
            patch("motor.core.agents.reparador.urllib.request.urlopen", return_value=resp),
        ):
            assert rep._nivel_3(f) is True
        assert f.read_text() == "x = 6"

    def test_respuesta_vacia_compila_vacio(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        resp = self._responde("")
        rep = AgenteReparador()
        with (
            patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(1, stderr="F821")),
            patch("motor.core.agents.reparador.urllib.request.urlopen", return_value=resp),
        ):
            assert rep._nivel_3(f) is True
        assert f.read_text() == ""

    def test_error_http_devuelve_false(self, tmp_path) -> None:
        f = tmp_path / "roto.py"
        f.write_text("print(x)\n")
        rep = AgenteReparador()
        with (
            patch("motor.core.agents.reparador.subprocess.run", return_value=_run_result(1, stderr="F821")),
            patch("motor.core.agents.reparador.urllib.request.urlopen", side_effect=OSError("conexion rechazada")),
        ):
            assert rep._nivel_3(f) is False
