"""Tests para core/mochila/guardian_opencode.py — OpenCodeGuardian."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from core.mochila.guardian_opencode import OpenCodeGuardian


@pytest.fixture
def guardian() -> OpenCodeGuardian:
    return OpenCodeGuardian(req_id="test-1")


class TestEvaluarTextoStream:
    def test_texto_normal_aprobado(self, guardian: OpenCodeGuardian) -> None:
        assert guardian.evaluar_texto_stream("def foo():\n    return 1") is True

    def test_un_pattern_aprobado(self, guardian: OpenCodeGuardian) -> None:
        txt = "// ... rest of the code\nprint(1)"
        assert guardian.evaluar_texto_stream(txt) is True

    def test_dos_patterns_rechazado(self, guardian: OpenCodeGuardian) -> None:
        txt = "// ... rest of the code\n// same as above\nprint(1)"
        assert guardian.evaluar_texto_stream(txt) is False

    def test_registra_ultimo_pattern(self, guardian: OpenCodeGuardian) -> None:
        guardian.evaluar_texto_stream("// unchanged\n// ... remaining")
        assert guardian._ultimo_pattern is not None


class TestGenerarPenalizacion:
    def test_sin_pattern_vacio(self, guardian: OpenCodeGuardian) -> None:
        assert guardian.generar_penalizacion() == ""

    def test_con_pattern(self, guardian: OpenCodeGuardian) -> None:
        guardian.evaluar_texto_stream("// unchanged\n# ... remaining")
        pena = guardian.generar_penalizacion()
        assert "RECHAZO DE INFRAESTRUCTURA" in pena
        assert guardian._ultimo_pattern in pena


class TestValidarDiff:
    def test_sin_problemas(self, guardian: OpenCodeGuardian) -> None:
        orig = "linea1\nlinea2\n"
        gen = "linea1\nlinea2\nlinea3\n"
        ok, problematicas = guardian.validar_diff(orig, gen)
        assert ok is True
        assert problematicas == []

    def test_con_una_problematica_aprobado(self, guardian: OpenCodeGuardian) -> None:
        orig = "linea1\n"
        gen = "linea1\n// ... rest of the code\n"
        ok, problematicas = guardian.validar_diff(orig, gen)
        assert ok is True  # 1 sola < 2
        assert len(problematicas) == 1

    def test_con_dos_problematicas_rechazado(self, guardian: OpenCodeGuardian) -> None:
        orig = "linea1\n"
        gen = "linea1\n// ... rest of the code\n// same as above\n"
        ok, problematicas = guardian.validar_diff(orig, gen)
        assert ok is False
        assert len(problematicas) == 2

    def test_sin_diff(self, guardian: OpenCodeGuardian) -> None:
        orig = "igual\n"
        ok, problematicas = guardian.validar_diff(orig, orig)
        assert ok is True
        assert problematicas == []


class TestVerificarSintaxis:
    def test_contenido_vacio(self, guardian: OpenCodeGuardian) -> None:
        assert guardian.verificar_sintaxis_final("x.py", "  \n") is False

    def test_menos_de_3_lineas(self, guardian: OpenCodeGuardian) -> None:
        assert guardian.verificar_sintaxis_final("x.py", "a\nb") is False

    def test_python_ok(self, guardian: OpenCodeGuardian, tmp_path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("def foo():\n    x = 1\n    return x\n")
        assert guardian.verificar_sintaxis_final(str(f), f.read_text()) is True

    def test_python_error(self, guardian: OpenCodeGuardian, tmp_path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("def foo(:\n    return 1\n")
        assert guardian.verificar_sintaxis_final(str(f), f.read_text()) is False

    def test_python_timeout(self, guardian: OpenCodeGuardian, monkeypatch, tmp_path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("a=1\nb=2\nc=3\n")
        monkeypatch.setattr("core.mochila.guardian_opencode.subprocess.run", mock.Mock(side_effect=__import__("subprocess").TimeoutExpired("py", 5)))
        assert guardian.verificar_sintaxis_final(str(f), f.read_text()) is False

    def test_shell_ok(self, guardian: OpenCodeGuardian, tmp_path) -> None:
        f = tmp_path / "x.sh"
        f.write_text("#!/bin/bash\nset -e\necho hola\n")
        with mock.patch("core.mochila.guardian_opencode.shutil.which", return_value="/bin/bash"):
            with mock.patch("core.mochila.guardian_opencode.subprocess.run", return_value=SimpleNamespace(returncode=0)):
                assert guardian.verificar_sintaxis_final(str(f), f.read_text()) is True

    def test_shell_sin_bash_retorna_true(self, guardian: OpenCodeGuardian, tmp_path) -> None:
        """Sin bash el codigo cae al return True final (no valida)."""
        f = tmp_path / "x.sh"
        f.write_text("#!/bin/bash\nset -e\necho hola\n")
        with mock.patch("core.mochila.guardian_opencode.shutil.which", return_value=None):
            assert guardian.verificar_sintaxis_final(str(f), f.read_text()) is True

    def test_json_ok(self, guardian: OpenCodeGuardian) -> None:
        assert guardian.verificar_sintaxis_final("c.json", '{\n  "a": 1\n}\n') is True

    def test_json_error(self, guardian: OpenCodeGuardian) -> None:
        assert guardian.verificar_sintaxis_final("c.json", '{\n  "a": }\n') is False

    def test_yaml_ok(self, guardian: OpenCodeGuardian, monkeypatch) -> None:
        fake_yaml = mock.Mock()
        fake_yaml.safe_load.return_value = {}
        monkeypatch.setitem(__import__("sys").modules, "yaml", fake_yaml)
        assert guardian.verificar_sintaxis_final("c.yaml", "a: 1\nb: 2\nc: 3\n") is True

    def test_yaml_sin_yaml_fallback(self, guardian: OpenCodeGuardian, monkeypatch) -> None:
        """Fallback ':' en contenido solo cuando yaml no importa (ImportError)."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "yaml":
                raise ImportError("no yaml")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert guardian.verificar_sintaxis_final("c.yml", "a: 1\nb: 2\nc: 3\n") is True
        assert guardian.verificar_sintaxis_final("c.yml", "sin\ndos\npuntos\n") is False

    def test_extension_desconocida_ok(self, guardian: OpenCodeGuardian) -> None:
        assert guardian.verificar_sintaxis_final("x.txt", "linea1\nlinea2\nlinea3\n") is True
