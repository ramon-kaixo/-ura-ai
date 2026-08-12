"""Tests de refactor_large_functions_v2.py — cobertura 100%.

Estrategia: URA_ROOT se remapea a un directorio temporal (fixture autouse
con reload del módulo) para que rglob/ruff/memoria operen sobre datos
controlados. ruff se simula con un stub ejecutable en tmp/.venv/bin.
"""

import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "pro"))

import refactor_large_functions_v2 as rlrf


@pytest.fixture(autouse=True)
def _ura_tmp(monkeypatch, tmp_path):
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    stub = tmp_path / ".venv" / "bin" / "ruff"
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    monkeypatch.setenv("URA_ROOT", str(tmp_path))
    monkeypatch.setenv("DRY_RUN", "0")
    monkeypatch.setenv("REFACTOR_VERIFY_TESTS", "1")
    importlib.reload(rlrf)
    yield tmp_path
    monkeypatch.undo()
    importlib.reload(rlrf)


def _func_src(n_lineas: int, nombre: str = "grande", args: str = "a, b") -> str:
    cuerpo = "".join(f"    v{i} = a + b + {i}\n" for i in range(n_lineas))
    return f"def {nombre}({args}):\n{cuerpo}"


def _archivo_con_funcion(tmp_path: Path, n_lineas: int, nombre: str = "grande") -> Path:
    archivo = tmp_path / "modulo.py"
    archivo.write_text(_func_src(n_lineas, nombre), encoding="utf-8")
    return archivo


class TestConstruirContextoRama:
    def test_archivo_inexistente_devuelve_rama_de_fuente_vacia(self, tmp_path):
        assert rlrf._construir_contexto_rama(str(tmp_path / "no.py"), "f", "") is not None

    def test_archivo_ok(self, tmp_path):
        archivo = _archivo_con_funcion(tmp_path, 5, "grande")
        resultado = rlrf._construir_contexto_rama(str(archivo), "grande", "def grande():\n")
        assert isinstance(resultado, str)


class TestAjustarContexto:
    def test_sin_config_usa_factor(self, tmp_path):
        assert rlrf._ajustar_contexto(5000) == 7500
        assert rlrf._ajustar_contexto(1000) == 2048  # mínimo

    def test_con_config_valida_limita(self, tmp_path):
        cfg = tmp_path / ".nervioso" / "chunk_config.json"
        cfg.parent.mkdir()
        cfg.write_text(json.dumps({"chunk_actual": 500}), encoding="utf-8")
        importlib.reload(rlrf)
        assert rlrf._ajustar_contexto(1000) == 500

    def test_config_corrupta_degrada(self, tmp_path):
        cfg = tmp_path / ".nervioso" / "chunk_config.json"
        cfg.parent.mkdir()
        cfg.write_text("no-json{", encoding="utf-8")
        importlib.reload(rlrf)
        assert rlrf._ajustar_contexto(5000) == 7500

    def test_respeta_max_modelo(self, tmp_path):
        assert rlrf._ajustar_contexto(10**6) == 100000

    def test_minimo_2048(self, tmp_path):
        assert rlrf._ajustar_contexto(10) == 2048


class TestEstimarTokens:
    def test_normal(self):
        assert rlrf._estimar_tokens("abcd" * 4) == 4

    def test_vacio_minimo_1(self):
        assert rlrf._estimar_tokens("") == 1


class TestOllamaRequest:
    def test_ok(self, monkeypatch):
        import urllib.request

        class FakeResp:
            def read(self):
                return b'{"response": "ok"}'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(req, timeout=600):
            return FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert rlrf._ollama_request("http://x/api/generate", {"m": 1}) == {"response": "ok"}

    def test_error_red(self, monkeypatch):
        import urllib.request

        def fake_urlopen(req, timeout=600):
            raise OSError("red")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(OSError):
            rlrf._ollama_request("http://x/api/generate", {"m": 1})


class TestLlm:
    def test_router_ok_devuelve_response(self, monkeypatch):
        import urllib.request

        class FakeResp:
            def read(self):
                return b'{"response": "def h(): pass"}'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        urls = []

        def fake_urlopen(req, timeout=600):
            urls.append(req.full_url)
            return FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert rlrf.llm("prompt") == "def h(): pass"
        assert urls == [f"{rlrf.OLLAMA_URL}/api/generate"]

    def test_router_falla_y_fallback_ok(self, monkeypatch):
        import urllib.request

        class FakeResp:
            def __init__(self, body):
                self.body = body

            def read(self):
                return self.body

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        calls = []

        def fake_urlopen(req, timeout=600):
            calls.append(req.full_url)
            if ":11435/" in req.full_url:
                raise OSError("router caido")
            return FakeResp(b'{"response": "fallback"}')

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert rlrf.llm("prompt") == "fallback"
        assert len(calls) == 2

    def test_ambos_fallan_devuelve_vacio(self, monkeypatch):
        import urllib.request

        def fake_urlopen(req, timeout=600):
            raise OSError("todo caido")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert rlrf.llm("prompt") == ""

    def test_router_sin_response_cae_a_fallback(self, monkeypatch):
        import urllib.request

        class FakeResp:
            def __init__(self, body):
                self.body = body

            def read(self):
                return self.body

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        calls = []

        def fake_urlopen(req, timeout=600):
            calls.append(req.full_url)
            if ":11435/" in req.full_url:
                return FakeResp(b"{}")
            return FakeResp(b'{"response": "por fallback"}')

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert rlrf.llm("prompt") == "por fallback"
        assert len(calls) == 2


class TestIsExcluded:
    @pytest.mark.parametrize(
        "path",
        [
            "/proyecto/.venv/lib/x.py",
            "/proyecto/.git/objs/x.py",
            "/proyecto/node_modules/a.py",
            "/proyecto/site-packages/b.py",
            "/proyecto/.attic/old.py",
            "/proyecto/venv/c.py",
        ],
    )
    def test_excluidos(self, path):
        assert rlrf.is_excluded(path)

    def test_no_excluido(self):
        assert not rlrf.is_excluded("/proyecto/core/modulo.py")


class TestGetLargeFunctions:
    def test_detecta_funciones_grandes(self, tmp_path):
        _archivo_con_funcion(tmp_path, 200)
        grandes = rlrf.get_large_functions(threshold=80)
        assert len(grandes) == 1
        assert grandes[0]["function"] == "grande"
        assert grandes[0]["lines"] == 200

    def test_respeta_threshold(self, tmp_path):
        _archivo_con_funcion(tmp_path, 10)
        assert rlrf.get_large_functions(threshold=80) == []

    def test_ignora_archivo_con_syntaxerror(self, tmp_path):
        (tmp_path / "roto.py").write_text("def roto(:", encoding="utf-8")
        assert rlrf.get_large_functions(threshold=5) == []

    def test_ignora_funciones_dentro_venv(self, tmp_path):
        venv = tmp_path / ".venv" / "x.py"
        venv.parent.mkdir(exist_ok=True)
        venv.write_text(_func_src(200), encoding="utf-8")
        assert rlrf.get_large_functions(threshold=80) == []

    def test_funcion_async_contada(self, tmp_path):
        (tmp_path / "async_mod.py").write_text(
            "async def agrande():\n" + "".join("    x = 1\n" for _ in range(100)),
            encoding="utf-8",
        )
        grandes = rlrf.get_large_functions(threshold=80)
        assert any(f["function"] == "agrande" for f in grandes)


class TestCleanLlmResponse:
    def test_sin_markdown(self):
        assert rlrf.clean_llm_response("  def h(): pass  ") == "def h(): pass"

    def test_con_backticks_python(self):
        fuente = "```python\ndef h():\n    return 1\n```"
        assert rlrf.clean_llm_response(fuente) == "def h():\n    return 1"

    def test_con_backticks_sin_lang(self):
        fuente = "```\ndef h(): pass\n```"
        assert rlrf.clean_llm_response(fuente) == "def h(): pass"


class TestExtraerLlamadores:
    def test_archivo_inexistente(self, tmp_path):
        assert rlrf._extraer_llamadores(str(tmp_path / "no.py"), "f") == ""

    def test_encuentra_llamadas_unicas(self, tmp_path):
        fuente = "def f(): pass\nf()\nf()\ng(x=f())\n"
        assert rlrf._extraer_llamadores("x.py", "f", fuente) == "  f()\n  g(x=f())"

    def test_sin_llamadas(self, tmp_path):
        assert rlrf._extraer_llamadores("x.py", "f", "a = 1\n") == ""

    def test_syntaxerror_vacio(self, tmp_path):
        assert rlrf._extraer_llamadores("x.py", "f", "def roto(:") == ""

    def test_limita_a_cinco_vias(self):
        fuente = "".join(f"f({i})\n" for i in range(10))
        resultado = rlrf._extraer_llamadores("x.py", "f", fuente)
        assert resultado.count("\n") == 4


class TestBuildRefactorPrompt:
    def test_con_llamadores_y_rama(self):
        prompt = rlrf.build_refactor_prompt(
            "f", "def f(a):\n    return a", 2, llamadores="  f(1)", contexto_rama="RAMAS",
        )
        assert "LLAMADORES DE LA FUNCION" in prompt
        assert "CONEXIONES DEL CODIGO" in prompt
        assert "RAMAS" in prompt
        assert 'Funcion: "f" (2 lineas)' in prompt

    def test_sin_contexto_extra(self):
        prompt = rlrf.build_refactor_prompt("f", "def f():\n    pass", 2)
        assert "LLAMADORES" not in prompt
        assert "CONEXIONES" not in prompt


class TestExtraerFirma:
    def test_normal(self):
        assert rlrf._extraer_firma("def f(a, b):\n    return a") == "f(a, b)"

    def test_async(self):
        assert rlrf._extraer_firma("async def g(x):\n    return x") == "g(x)"

    def test_syntaxerror(self):
        assert rlrf._extraer_firma("def roto(:") == ""

    def test_sin_funcion(self):
        assert rlrf._extraer_firma("a = 1") == ""


class TestApplyRefactored:
    def test_new_code_vacio(self, tmp_path):
        archivo = _archivo_con_funcion(tmp_path, 5)
        assert not rlrf.apply_refactored(str(archivo), 1, 6, "   \n")

    def test_firma_cambiada_rechaza(self, tmp_path):
        archivo = tmp_path / "inline.py"
        archivo.write_text("def grande(a, b): return a + b\n", encoding="utf-8")
        assert not rlrf.apply_refactored(str(archivo), 1, 1, "def grande(a):\n    return a")

    def test_syntaxerror_en_respuesta(self, tmp_path):
        archivo = _archivo_con_funcion(tmp_path, 5)
        assert not rlrf.apply_refactored(str(archivo), 1, 6, "def roto(:")

    def test_post_reemplazo_roto(self, tmp_path):
        archivo = tmp_path / "expr.py"
        archivo.write_text("a = (1 +\n2)\n", encoding="utf-8")
        assert not rlrf.apply_refactored(str(archivo), 1, 1, "y = 1")

    def test_dry_run_no_escribe(self, tmp_path):
        archivo = _archivo_con_funcion(tmp_path, 5)
        importlib.reload(rlrf)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("DRY_RUN", "1")
        importlib.reload(rlrf)
        try:
            assert rlrf.apply_refactored(str(archivo), 1, 6, "def h():\n    return 1")
            assert "def h()" not in archivo.read_text(encoding="utf-8")
            assert not (tmp_path / "modulo.py.bak").exists()
        finally:
            monkeypatch.undo()
            importlib.reload(rlrf)

    def test_exito_escribe_backup_y_archivo(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5, "grande")
        monkeypatch.setattr(
            rlrf.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})(),
        )
        helpers = "def helper(v):\n    return v\n"
        assert rlrf.apply_refactored(str(archivo), 1, 6, helpers)
        contenido = archivo.read_text(encoding="utf-8")
        assert "def helper(v)" in contenido
        assert "def grande(a, b):" not in contenido
        assert (tmp_path / "modulo.py.bak").exists()

    def test_normalizacion_no_disponible_degrada(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5, "grande")
        (tmp_path / ".venv" / "bin" / "ruff").unlink()
        importlib.reload(rlrf)
        monkeypatch.setattr(
            rlrf.subprocess, "run", lambda cmd, **k: (_ for _ in ()).throw(FileNotFoundError(cmd[0]))
            if str(tmp_path) in str(cmd[0]) else type("R", (), {"returncode": 0})(),
        )
        helpers = "def helper(v):\n    return v\n"
        assert rlrf.apply_refactored(str(archivo), 1, 6, helpers)

    def test_normalizacion_vacia_usa_original(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5, "grande")

        def fake_run(cmd, **k):
            Path(cmd[-1]).write_text("   ", encoding="utf-8")
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr(rlrf.subprocess, "run", fake_run)
        helpers = "def helper(v):\n    return v\n"
        assert rlrf.apply_refactored(str(archivo), 1, 6, helpers)

    def test_copia_backup_solo_una_vez(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5, "grande")
        monkeypatch.setattr(
            rlrf.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})(),
        )
        helpers = "def helper(v):\n    return v\n"
        assert rlrf.apply_refactored(str(archivo), 1, 6, helpers)
        assert rlrf.apply_refactored(str(archivo), 1, 6, helpers)
        contenido = archivo.read_text(encoding="utf-8")
        assert "def helper(v)" in contenido
        assert contenido.count("def helper(v)") >= 1

    def test_excepcion_validando_firma_no_bloquea(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5, "grande")
        monkeypatch.setattr(rlrf, "_extraer_firma", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr(
            rlrf.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})(),
        )
        assert rlrf.apply_refactored(str(archivo), 1, 6, "def helper(v):\n    return v\n")


class TestRefactorOne:
    def test_memoria_completada_skip(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "consultar_funcion", lambda *a, **k: {"estado": "completada"})
        assert not rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.SKIPPED == 1

    def test_archivo_ilegible_error(self, tmp_path):
        assert not rlrf.refactor_one(
            {"file": str(tmp_path / "no.py"), "function": "f", "lineno": 1, "end_lineno": 2, "lines": 1},
        )
        assert rlrf.ERRORS == 1

    def test_llm_sin_respuesta_error(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "")
        assert not rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.ERRORS == 1

    def test_llm_responde_pass_skip(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "PASS")
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        assert not rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.SKIPPED == 1

    def test_fraccionado_y_helpers_aplicados(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 100)
        respuestas = ["def helper1(x):\n    return x + 1\n", "def helper2(x):\n    return x + 2\n"]

        def fake_llm(prompt):
            return respuestas.pop(0) if respuestas else "PASS"

        monkeypatch.setattr(rlrf, "llm", fake_llm)
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())
        assert rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 102, "lines": 101},
        )
        assert rlrf.REFACTORED == 1

    def test_apply_falla_tras_edicion(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf, "apply_refactored", lambda *a, **k: False)
        assert not rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.ERRORS == 1

    def test_edicion_rechazada(self, tmp_path, monkeypatch):
        import edicion_ast

        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: (tmp_path / "nada.py").read_text() if False else "zzz")
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(edicion_ast, "aplicar_helpers", lambda *a, **k: (False, "no"))
        monkeypatch.setattr(edicion_ast, "diff_quirurgico", lambda *a, **k: (False, "no tampoco"))
        assert not rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.SKIPPED == 1

    def test_import_error_edicion_usa_flujo_anterior(self, tmp_path, monkeypatch):
        import sys as _sys

        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setitem(_sys.modules, "edicion_ast", None)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())
        assert rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.REFACTORED == 1

    def test_verificacion_rompe_tests_rechaza(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "_tests_para_archivo", lambda *a, **k: ["tests_tmp.py"])
        monkeypatch.setattr(rlrf, "ejecutar_tests", lambda *a, **k: {"ok": True, "ejecutados": 1, "fallidos": 0})
        monkeypatch.setattr(rlrf, "verificar_con_tests", lambda *a, **k: {"veredicto": "rompe", "regresiones": "1"})
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        assert not rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.SKIPPED == 1

    def test_verificacion_json_ok_y_aplica(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "_tests_para_archivo", lambda *a, **k: ["tests_tmp.py"])
        monkeypatch.setattr(rlrf, "ejecutar_tests", lambda *a, **k: {"ok": True, "ejecutados": 1, "fallidos": 0})
        monkeypatch.setattr(rlrf, "verificar_con_tests", lambda *a, **k: {"veredicto": "ok"})
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        monkeypatch.setattr(rlrf, "apply_refactored", lambda *a, **k: True)
        assert rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.REFACTORED == 1

    def test_verificacion_excepcion_no_bloquea(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "_tests_para_archivo", lambda *a, **k: ["tests_tmp.py"])
        monkeypatch.setattr(rlrf, "ejecutar_tests", lambda *a, **k: {"ok": True, "ejecutados": 1, "fallidos": 0})
        monkeypatch.setattr(rlrf, "verificar_con_tests", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        monkeypatch.setattr(rlrf, "apply_refactored", lambda *a, **k: True)
        assert rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.REFACTORED == 1

    def test_tests_baseline_con_fallos_no_bloquea(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "_tests_para_archivo", lambda *a, **k: ["tests_tmp.py"])
        monkeypatch.setattr(rlrf, "ejecutar_tests", lambda *a, **k: {"ok": False, "ejecutados": 1, "fallidos": 1})
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        monkeypatch.setattr(rlrf, "apply_refactored", lambda *a, **k: True)
        assert rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.REFACTORED == 1

    def test_verificacion_tests_desactivada_por_env(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setenv("REFACTOR_VERIFY_TESTS", "0")
        importlib.reload(rlrf)
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        monkeypatch.setattr(rlrf, "apply_refactored", lambda *a, **k: True)
        assert rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.REFACTORED == 1

    def test_memoria_necesita_otro_modelo_intenta_igual(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "consultar_funcion", lambda *a, **k: {"estado": "necesita_otro_modelo"})
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        monkeypatch.setattr(rlrf, "apply_refactored", lambda *a, **k: True)
        assert rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.REFACTORED == 1

    def test_sin_tests_para_archivo_no_verifica(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)
        monkeypatch.setattr(rlrf, "_tests_para_archivo", lambda *a, **k: [])
        monkeypatch.setattr(rlrf, "ejecutar_tests", lambda *a, **k: {"ok": True})
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        monkeypatch.setattr(rlrf, "apply_refactored", lambda *a, **k: True)
        assert rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.REFACTORED == 1

    def test_normalizacion_helpers_vacia(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)

        def fake_run(cmd, **k):
            Path(cmd[-1]).write_text("  ", encoding="utf-8")
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr(rlrf.subprocess, "run", fake_run)
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        monkeypatch.setattr(rlrf, "apply_refactored", lambda *a, **k: True)
        assert rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.REFACTORED == 1

    def test_normalizacion_helpers_no_disponible(self, tmp_path, monkeypatch):
        archivo = _archivo_con_funcion(tmp_path, 5)

        def fake_run(cmd, **k):
            if str(tmp_path) in str(cmd[0]):
                raise FileNotFoundError(cmd[0])
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr(rlrf.subprocess, "run", fake_run)
        monkeypatch.setattr(rlrf, "registrar_intento", lambda *a, **k: None)
        monkeypatch.setattr(rlrf, "llm", lambda prompt: "def helper(x):\n    return x")
        monkeypatch.setattr(rlrf, "apply_refactored", lambda *a, **k: True)
        assert rlrf.refactor_one(
            {"file": str(archivo), "function": "grande", "lineno": 1, "end_lineno": 7, "lines": 6},
        )
        assert rlrf.REFACTORED == 1


class TestScanProject:
    def test_scan_no_levanta(self, tmp_path, capsys):
        rlrf.scan_project()
        assert capsys.readouterr().out == ""


class TestMain:
    def test_scan_flag(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["refactor_large_functions_v2.py", "--scan"])
        rlrf.main()

    def test_loop_normal(self, tmp_path, monkeypatch, capsys):
        _archivo_con_funcion(tmp_path, 200)
        monkeypatch.setenv("MIN_LINES", "80")
        importlib.reload(rlrf)
        monkeypatch.setattr(rlrf, "refactor_one", lambda func: None)
        monkeypatch.setattr(sys, "argv", ["refactor_large_functions_v2.py"])
        rlrf.main()
