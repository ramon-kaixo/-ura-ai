"""Tests para scripts/pro/tuneladora/shadow/layer3_shadow.py."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts.pro.tuneladora.shadow.layer3_shadow import (
    _extract_callables,
    _git_show,
    run,
)


class TestGitShow:
    def test_ok(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.layer3_shadow.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout="contenido viejo"),
        )
        assert _git_show("a.py", tmp_path) == "contenido viejo"

    def test_rc_no_cero(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.layer3_shadow.subprocess.run",
            lambda *a, **k: SimpleNamespace(returncode=128, stdout=""),
        )
        assert _git_show("a.py", tmp_path) == ""

    def test_error(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.layer3_shadow.subprocess.run",
            mock.Mock(side_effect=OSError("x")),
        )
        assert _git_show("a.py", tmp_path) == ""


class TestExtractCallables:
    def test_funciones_y_metodos(self) -> None:
        src = "def foo(a, b):\n    pass\n\nclass Bar:\n    def baz(self, x):\n        pass\n"
        funcs = _extract_callables(src)
        names = {f["name"] for f in funcs}
        assert names == {"foo", "Bar.baz"}
        foo = next(f for f in funcs if f["name"] == "foo")
        assert foo["args"] == ["a", "b"]

    def test_syntax_error_vacio(self) -> None:
        assert _extract_callables("def roto(:\n") == []

    def test_async_funcion(self) -> None:
        src = "async def main():\n    pass\n"
        funcs = _extract_callables(src)
        assert funcs[0]["name"] == "main"


class TestRun:
    def test_no_python_skip(self, tmp_path: Path) -> None:
        results = run(["a.txt"], tmp_path)
        assert results[0].status == "SKIP"
        assert "Not a Python file" in results[0].detail

    def test_archivo_no_encontrado(self, tmp_path: Path) -> None:
        results = run(["no/existe.py"], tmp_path)
        assert results[0].status == "SKIP"
        assert "File not found" in results[0].detail

    def test_archivo_nuevo_sin_previo(self, tmp_path: Path) -> None:
        f = tmp_path / "nuevo.py"
        f.write_text("def x():\n    pass\n")
        with mock.patch("scripts.pro.tuneladora.shadow.layer3_shadow._git_show", return_value=""):
            results = run(["nuevo.py"], tmp_path)
        assert results[0].status == "OK"
        assert "New file" in results[0].detail

    def test_sin_cambios(self, tmp_path: Path) -> None:
        f = tmp_path / "igual.py"
        f.write_text("def x():\n    pass\n")
        with mock.patch("scripts.pro.tuneladora.shadow.layer3_shadow._git_show", return_value="def x():\n    pass\n"):
            results = run(["igual.py"], tmp_path)
        assert results[0].status == "OK"
        assert "No changes" in results[0].detail

    def test_funcion_eliminada_warn(self, tmp_path: Path) -> None:
        f = tmp_path / "cambio.py"
        f.write_text("def nuevo():\n    pass\n")
        with mock.patch("scripts.pro.tuneladora.shadow.layer3_shadow._git_show", return_value="def viejo():\n    pass\n"):
            results = run(["cambio.py"], tmp_path)
        assert results[0].status == "WARN"
        assert "removed" in results[0].detail

    def test_funcion_nueva_ok(self, tmp_path: Path) -> None:
        f = tmp_path / "agrega.py"
        f.write_text("def existente():\n    pass\ndef nueva():\n    pass\n")
        with mock.patch("scripts.pro.tuneladora.shadow.layer3_shadow._git_show", return_value="def existente():\n    pass\n"):
            results = run(["agrega.py"], tmp_path)
        assert results[0].status == "OK"
        assert "1 new functions" in results[0].detail

    def test_args_cambiados_warn(self, tmp_path: Path) -> None:
        f = tmp_path / "firma.py"
        f.write_text("def foo(a, b, c):\n    pass\n")
        with mock.patch("scripts.pro.tuneladora.shadow.layer3_shadow._git_show", return_value="def foo(a):\n    pass\n"):
            results = run(["firma.py"], tmp_path)
        assert results[0].status == "WARN"
        assert "args_changed" in results[0].detail
