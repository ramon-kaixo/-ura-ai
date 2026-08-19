"""Tests de motor/assistant/executor.py (cobertura 0% -> objetivo >=90%)."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from motor.assistant.executor import (
    CalculatorTool,
    ConversationalToolManager,
    DateTimeTool,
    DockerTool,
    FileReadTool,
    GitBranchTool,
    GitCommitTool,
    GitTool,
    NewsTool,
    NoteTool,
    SystemInfoTool,
    ToolResult,
    WeatherTool,
    _SafeCalculator,
)


def _result(returncode: int = 0, stdout: str = "out", stderr: str = "err") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class TestToolResult:
    def test_ok(self) -> None:
        r = ToolResult(True, "out")
        assert r.success and r.output == "out" and r.error == ""
        assert r.to_dict() == {"success": True, "output": "out", "error": ""}

    def test_error(self) -> None:
        r = ToolResult(False, error="boom")
        assert not r.success and r.output == "" and r.error == "boom"
        assert r.to_dict()["error"] == "boom"


class TestGitTool:
    def test_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(stdout="M file.py"))
        r = GitTool().status()
        assert r.success and r.output == "M file.py"

    def test_status_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=OSError("no git")))
        r = GitTool().status()
        assert not r.success and r.error == "no git"

    def test_log(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(stdout="abc123 feat"))
        r = GitTool().log(3)
        assert r.success and r.output == "abc123 feat"

    def test_log_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=TimeoutError("lento")))
        r = GitTool().log()
        assert not r.success and r.error == "lento"

    def test_diff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(stdout="2 files"))
        r = GitTool().diff()
        assert r.success and r.output == "2 files"

    def test_diff_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=OSError("x")))
        r = GitTool().diff()
        assert not r.success


class TestGitBranchTool:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(stdout="* main"))
        r = GitBranchTool().execute("")
        assert r.success and r.output == "* main"

    def test_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=OSError("boom")))
        (tmp_path / ".git").mkdir()
        r = GitBranchTool().execute(str(tmp_path))
        assert not r.success and r.error == "boom"

    def test_repo_invalido(self) -> None:
        """Un repo inexistente se rechaza antes de tocar subprocess."""
        r = GitBranchTool().execute("/no/existe/repo")
        assert not r.success and "Repo inválido" in r.error


class TestGitCommitTool:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(0, "committed", "err"))
        r = GitCommitTool().execute("msg")
        assert r.success and r.output == "committed"

    def test_falla_returncode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(1, "", "nada que commitear"))
        r = GitCommitTool().execute("msg")
        assert not r.success and r.output == "nada que commitear"

    def test_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=OSError("boom")))
        r = GitCommitTool().execute("msg")
        assert not r.success and r.error == "boom"


class TestDockerTool:
    def test_ps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(stdout="s1 Up"))
        r = DockerTool().ps()
        assert r.success and r.output == "s1 Up"

    def test_ps_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=OSError("no docker")))
        r = DockerTool().ps()
        assert not r.success

    def test_logs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(stdout="", stderr="log line"))
        r = DockerTool().logs("c1", 10)
        assert r.success and r.output == "log line"

    def test_logs_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=OSError("boom")))
        r = DockerTool().logs("c1")
        assert not r.success


class TestFileReadTool:
    def test_denegado(self) -> None:
        r = FileReadTool().execute("/tmp/otra_cosa.txt")
        assert not r.success and "Acceso denegado" in r.error

    def test_no_existe(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        r = FileReadTool().execute(str(tmp_path / ".ura" / "nope.txt"))
        assert not r.success and "no encontrado" in r.error

    def test_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        f = tmp_path / ".ura" / "ok.txt"
        f.parent.mkdir(exist_ok=True)
        f.write_text("contenido")
        r = FileReadTool().execute(str(f))
        assert r.success and r.output == "contenido"

    def test_error_lectura(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        f = tmp_path / ".ura" / "r.txt"
        f.parent.mkdir(exist_ok=True)
        f.write_text("x")
        with mock.patch("pathlib.Path.read_text", side_effect=OSError("permiso")):
            r = FileReadTool().execute(str(f))
        assert not r.success and r.error == "permiso"


class TestSystemInfoTool:
    def test_psutil(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = SimpleNamespace(
            virtual_memory=lambda: SimpleNamespace(used=2**31, total=8**30, percent=25),
            cpu_percent=lambda interval=0.1: 5.0,
            disk_usage=lambda _: SimpleNamespace(used=2**30, total=4**30, percent=50),
        )
        monkeypatch.setitem(sys.modules, "psutil", fake)
        r = SystemInfoTool().execute()
        assert r.success and "RAM" in r.output and "CPU" in r.output and "Disco" in r.output

    def test_sin_psutil(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with mock.patch.dict(sys.modules, {"psutil": None}):
            r = SystemInfoTool().execute()
        assert r.success and "RAM" in r.output


class TestSafeCalculator:
    def _eval(self, expr: str) -> str:
        return _SafeCalculator().evaluate(expr)

    def test_aritmetica(self) -> None:
        assert self._eval("2 + 3 * 4") == "14"
        assert self._eval("10 - 3") == "7"
        assert self._eval("8 / 4") == "2"
        assert self._eval("7 // 2") == "3"
        assert self._eval("7 % 3") == "1"
        assert self._eval("2 ** 10") == "1024"

    def test_unario(self) -> None:
        assert self._eval("-5") == "-5"
        assert self._eval("+3") == "3"

    def test_funciones_math(self) -> None:
        assert self._eval("sqrt(16)") == "4"
        assert self._eval("abs(-9)") == "9"
        assert self._eval("max(1, 5, 3)") == "5"
        assert self._eval("round(3.7)") == "4"

    def test_float_integro(self) -> None:
        assert self._eval("4.0") == "4"
        assert self._eval("1.5 + 1") == "2.5"

    def test_division_cero(self) -> None:
        with pytest.raises(ZeroDivisionError):
            self._eval("1 / 0")

    def test_nombre_no_definido(self) -> None:
        with pytest.raises(ValueError):
            self._eval("x + 1")

    def test_operador_no_soportado(self) -> None:
        with pytest.raises(ValueError):
            self._eval("1 @ 2")

    def test_llamada_no_permitida(self) -> None:
        with pytest.raises(ValueError):
            self._eval("open(1)")

    def test_syntax_error(self) -> None:
        with pytest.raises(SyntaxError):
            self._eval("1 +")

    def test_nodo_no_soportado(self) -> None:
        with pytest.raises(ValueError, match="no soportada"):
            self._eval("1 < 2")  # ast.Compare

    def test_operador_unario_no_soportado(self) -> None:
        with pytest.raises(ValueError, match="Operador no soportado"):
            self._eval("~3")  # ast.Invert

    def test_constante_numerica(self) -> None:
        assert self._eval("pi") == "3.141592653589793"
        assert self._eval("e") == "2.718281828459045"

    def test_nombre_funcion_no_permitida(self) -> None:
        with pytest.raises(ValueError, match="Funcion no permitida"):
            self._eval("sqrt")  # sqrt es callable, no numerico directo

    def test_resultado_no_numerico(self) -> None:
        with pytest.raises(ValueError, match="Resultado no numerico"):
            self._eval('max("abc")')  # constante str -> resultado str


class TestCalculatorTool:
    def test_vacio(self) -> None:
        r = CalculatorTool().execute("   ")
        assert not r.success and r.error == "No expression"

    def test_ok(self) -> None:
        r = CalculatorTool().execute("6 * 7")
        assert r.success and r.output == "42"

    def test_error(self) -> None:
        r = CalculatorTool().execute("1 / 0")
        assert not r.success and "Error" in r.error


class TestNoteTool:
    def test_save_y_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.assistant import config

        monkeypatch.setattr(config.config, "db_for", lambda name: str(tmp_path / f"{name}.db"))
        monkeypatch.setattr(config.config, "ensure_data_dir", lambda: None)
        t = NoteTool()
        r = t.save("hola nota")
        assert r.success and r.output == "Nota guardada"
        r2 = t.save("segunda nota")
        assert r2.success
        lst = t.list_recent(5)
        assert lst.success and "segunda nota" in lst.output and "hola nota" in lst.output

    def test_list_vacia(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.assistant import config

        monkeypatch.setattr(config.config, "db_for", lambda name: str(tmp_path / f"{name}.db"))
        monkeypatch.setattr(config.config, "ensure_data_dir", lambda: None)
        r = NoteTool().list_recent()
        assert r.success and r.output == "No hay notas guardadas"

    def test_truncado_500(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.assistant import config

        monkeypatch.setattr(config.config, "db_for", lambda name: str(tmp_path / f"{name}.db"))
        monkeypatch.setattr(config.config, "ensure_data_dir", lambda: None)
        t = NoteTool()
        t.save("x" * 2000)
        conn = sqlite3.connect(str(tmp_path / "notes.db"))
        row = conn.execute("SELECT content FROM notes").fetchone()
        assert len(row[0]) == 500


class TestDateTimeTool:
    def test_formato(self) -> None:
        r = DateTimeTool().execute()
        assert r.success and r.output.startswith("Son las ")


class TestWeatherTool:
    def test_sin_location_ipapi(self) -> None:
        async def go() -> None:
            m_get = mock.Mock(
                side_effect=[
                    SimpleNamespace(json=lambda: {"city": "Bilbao"}),
                    SimpleNamespace(status_code=200, text="Bilbao: 15C"),
                ]
            )
            with mock.patch("motor.assistant.executor.httpx.get", m_get):
                r = await WeatherTool().execute()
            assert r.success and "Bilbao" in r.output
            assert m_get.call_args_list[0][0][0] == "https://ipapi.co/json/"

        asyncio.run(go())

    def test_sin_location_fallback(self) -> None:
        async def go() -> None:
            m_get = mock.Mock(
                side_effect=[
                    OSError("sin red"),
                    SimpleNamespace(status_code=200, text="Madrid: 20C"),
                ]
            )
            with mock.patch("motor.assistant.executor.httpx.get", m_get):
                r = await WeatherTool().execute()
            assert r.success and "Madrid" in r.output

        asyncio.run(go())

    def test_status_error(self) -> None:
        async def go() -> None:
            m_get = mock.Mock(return_value=SimpleNamespace(status_code=500, text=""))
            with mock.patch("motor.assistant.executor.httpx.get", m_get):
                r = await WeatherTool().execute("Bilbao")
            assert not r.success and "Error clima" in r.error

        asyncio.run(go())

    def test_exception(self) -> None:
        async def go() -> None:
            m_get = mock.Mock(side_effect=OSError("red caida"))
            with mock.patch("motor.assistant.executor.httpx.get", m_get):
                r = await WeatherTool().execute("Bilbao")
            assert not r.success and r.error == "red caida"

        asyncio.run(go())


class TestNewsTool:
    def test_ok(self) -> None:
        async def go() -> None:
            m_get = mock.Mock(
                return_value=SimpleNamespace(
                    status_code=200,
                    text="<title>Noticia 1</title><title>Noticia 2</title>",
                )
            )
            with mock.patch("motor.assistant.executor.httpx.get", m_get):
                r = await NewsTool().execute()
            assert r.success and "Noticia 1" in r.output and "Noticia 2" in r.output

        asyncio.run(go())

    def test_status_error(self) -> None:
        async def go() -> None:
            m_get = mock.Mock(return_value=SimpleNamespace(status_code=404, text=""))
            with mock.patch("motor.assistant.executor.httpx.get", m_get):
                r = await NewsTool().execute()
            assert not r.success and "404" in r.error

        asyncio.run(go())

    def test_exception(self) -> None:
        async def go() -> None:
            m_get = mock.Mock(side_effect=OSError("boom"))
            with mock.patch("motor.assistant.executor.httpx.get", m_get):
                r = await NewsTool().execute()
            assert not r.success and r.error == "boom"

        asyncio.run(go())


class TestManager:
    @pytest.fixture
    def mgr(self) -> ConversationalToolManager:
        return ConversationalToolManager()

    async def _run(self, mgr: ConversationalToolManager, name: str, params: dict | None = None) -> ToolResult:
        return await mgr.execute(name, params)

    def test_git_status(self, mgr: ConversationalToolManager, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(stdout="M f.py"))
        r = asyncio.run(self._run(mgr, "git_status"))
        assert r.success and r.output == "M f.py"

    def test_git_log_params(self, mgr: ConversationalToolManager, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict = {}

        def fake_run(*a, **k):
            captured["args"] = a[0]
            return _result(stdout="log")

        monkeypatch.setattr("subprocess.run", fake_run)
        r = asyncio.run(self._run(mgr, "git_log", {"count": 3}))
        assert r.success and "git" in captured["args"]

    def test_docker_ps(self, mgr: ConversationalToolManager, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(stdout="c1 Up"))
        r = asyncio.run(self._run(mgr, "docker_ps"))
        assert r.success

    def test_datetime(self, mgr: ConversationalToolManager) -> None:
        r = asyncio.run(self._run(mgr, "datetime"))
        assert r.success

    def test_calculator(self, mgr: ConversationalToolManager) -> None:
        r = asyncio.run(self._run(mgr, "calculator", {"expression": "2+2"}))
        assert r.success and r.output == "4"

    def test_read_file(self, mgr: ConversationalToolManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        f = tmp_path / ".ura" / "a.txt"
        f.parent.mkdir(exist_ok=True)
        f.write_text("hi")
        r = asyncio.run(self._run(mgr, "read_file", {"path": str(f)}))
        assert r.success and r.output == "hi"

    def test_system_info(self, mgr: ConversationalToolManager, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = SimpleNamespace(
            virtual_memory=lambda: SimpleNamespace(used=2**31, total=8**30, percent=25),
            cpu_percent=lambda interval=0.1: 5.0,
            disk_usage=lambda _: SimpleNamespace(used=2**30, total=4**30, percent=50),
        )
        monkeypatch.setitem(sys.modules, "psutil", fake)
        r = asyncio.run(self._run(mgr, "system_info"))
        assert r.success

    def test_weather(self, mgr: ConversationalToolManager) -> None:
        async def go() -> ToolResult:
            with mock.patch(
                "motor.assistant.executor.httpx.get",
                mock.Mock(return_value=SimpleNamespace(status_code=200, text="Madrid: 20C")),
            ):
                return await mgr.execute("weather", {"location": "Madrid"})

        r = asyncio.run(go())
        assert r.success

    def test_news(self, mgr: ConversationalToolManager) -> None:
        async def go() -> ToolResult:
            with mock.patch(
                "motor.assistant.executor.httpx.get",
                mock.Mock(
                    return_value=SimpleNamespace(status_code=200, text="<title>A</title>")
                ),
            ):
                return await mgr.execute("news")

        r = asyncio.run(go())
        assert r.success

    def test_python(self, mgr: ConversationalToolManager, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", lambda *a, **k: _result(stdout="OK"))
        r = asyncio.run(self._run(mgr, "python", {"code": "print(1)"}))
        assert r.success and r.output == "OK"

    def test_python_sin_code(self, mgr: ConversationalToolManager) -> None:
        r = asyncio.run(self._run(mgr, "python"))
        assert not r.success and r.error == "No code"

    def test_web_search(self, mgr: ConversationalToolManager) -> None:
        async def go() -> ToolResult:
            with mock.patch("motor.assistant.executor.httpx.AsyncClient") as m_client:
                m_client.return_value.__aenter__.return_value.get.return_value = SimpleNamespace(
                    status_code=200,
                    text='<div class="result__snippet">hola mundo</div>',
                )
                return await mgr.execute("web_search", {"query": "ura"})

        r = asyncio.run(go())
        assert r.success and r.output == "hola mundo"

    def test_web_search_sin_query(self, mgr: ConversationalToolManager) -> None:
        r = asyncio.run(self._run(mgr, "web_search"))
        assert not r.success and r.error == "No query"

    def test_plugin_externo(self, mgr: ConversationalToolManager) -> None:
        async def go() -> ToolResult:
            plugin = mock.AsyncMock()
            plugin.execute.return_value = ToolResult(True, "plugin ok")
            mgr._plugins["mi_plugin"] = plugin
            return await mgr.execute("mi_plugin", {"x": 1})

        r = asyncio.run(go())
        assert r.success and r.output == "plugin ok"
        mgr._plugins["mi_plugin"].execute.assert_awaited_once()

    def test_load_plugins_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.assistant.tool_plugin

        monkeypatch.setattr(motor.assistant.tool_plugin, "discover_plugins", mock.Mock(side_effect=ImportError("x")))
        mgr = ConversationalToolManager()
        assert mgr._plugins == {}

    def test_not_found(self, mgr: ConversationalToolManager) -> None:
        r = asyncio.run(self._run(mgr, "no_existe"))
        assert not r.success and "not found" in r.error

    def test_web_search_error(self, mgr: ConversationalToolManager) -> None:
        async def go() -> ToolResult:
            with mock.patch("motor.assistant.executor.httpx.AsyncClient") as m_client:
                m_client.return_value.__aenter__.return_value.get = mock.AsyncMock(
                    side_effect=OSError("red caida")
                )
                return await mgr.execute("web_search", {"query": "ura"})

        r = asyncio.run(go())
        assert not r.success and r.error == "red caida"

    def test_python_error(self, mgr: ConversationalToolManager, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("subprocess.run", mock.Mock(side_effect=TimeoutError("lento")))
        r = asyncio.run(self._run(mgr, "python", {"code": "print(1)"}))
        assert not r.success and r.error == "lento"

    def test_needs_confirmation(self, mgr: ConversationalToolManager) -> None:
        assert mgr.needs_confirmation("python")
        assert mgr.needs_confirmation("git_commit")
        assert mgr.needs_confirmation("note_list", "borra todo")
        assert not mgr.needs_confirmation("git_status")
        assert not mgr.needs_confirmation("git_status", "ver estado")

    def test_list_tools(self, mgr: ConversationalToolManager) -> None:
        tools = mgr.list_tools()
        assert "git_status" in tools and "calculator" in tools and "note_save" in tools


import sys
