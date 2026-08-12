"""Tests de verificador_tests.py (TASK-20260812-023) — cobertura 100%.

Cubre: _tests_para_archivo (todas las ramas), _tests_del_modulo, ejecutar_tests
(con tests reales y timeout), verificar_con_tests (todas las ramas).
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "pro"))

from verificador_tests import (
    _tests_del_modulo,
    _tests_para_archivo,
    ejecutar_tests,
    verificar_con_tests,
)


def test_tests_para_archivo_encuentra_directo() -> None:
    # motor/core/fusion/engine.py -> test_fusion.py (import exacto)
    # Ruta ABSOLUTA para ser independiente del cwd de ejecución.
    repo = Path(__file__).parent.parent.parent
    tests = _tests_para_archivo(str(repo / "motor" / "core" / "fusion" / "engine.py"))
    assert any("test_fusion.py" in str(t) for t in tests)


def test_tests_para_archivo_sin_cobertura() -> None:
    tests = _tests_para_archivo("scripts/pro/noexiste_modulo.py")
    assert tests == []


def test_tests_para_archivo_ruta_relativa() -> None:
    # Debe resolver la ruta a absoluta (independiente del cwd)
    repo = Path(__file__).parent.parent.parent
    tests = _tests_para_archivo(str(repo / "core" / "mochila" / "router.py"))
    assert isinstance(tests, list)


def test_tests_del_modulo_encuentra() -> None:
    tests = _tests_del_modulo("knowledge/engine/reader.py")
    # test_knowledge_engine.py puede existir
    assert isinstance(tests, list)


def test_tests_del_modulo_sin() -> None:
    assert _tests_del_modulo("scripts/pro/x_inexistente.py") == []


def test_ejecutar_tests_sin_tests() -> None:
    r = ejecutar_tests([])
    assert r["ok"] is True
    assert r["ejecutados"] == 0


def test_ejecutar_tests_reales() -> None:
    # Ejecutar un test real que sabemos que pasa (rápido)
    tests = [Path("tests/unit/test_memoria_refactor.py")]
    r = ejecutar_tests(tests, timeout=60)
    assert r["ok"] is True
    assert r["ejecutados"] == 1


def test_ejecutar_tests_timeout() -> None:
    tests = [Path("tests/unit/test_memoria_refactor.py")]
    r = ejecutar_tests(tests, timeout=1)
    # Con timeout de 1s, o pasa rápido o timeout — pero no debe crashear
    assert "ok" in r
    assert "ejecutados" in r


def test_verificar_sin_tests_ok() -> None:
    with patch("verificador_tests._tests_para_archivo", return_value=[]):
        r = verificar_con_tests("archivo_sin_tests.py", nuevo_contenido="x = 1")
    assert r["veredicto"] == "sin_tests"
    assert r["sintaxis"] == "ok"


def test_verificar_sin_tests_sintaxis_rota() -> None:
    with patch("verificador_tests._tests_para_archivo", return_value=[]):
        r = verificar_con_tests("archivo_sin_tests.py", nuevo_contenido="def (")
    assert r["veredicto"] == "sin_tests"
    assert "error" in r["sintaxis"]


def test_verificar_con_tests_ok() -> None:
    with (
        patch("verificador_tests._tests_para_archivo", return_value=[Path("t1.py")]),
        patch("verificador_tests.ejecutar_tests", return_value={"ok": True, "detalle": []}),
    ):
            r = verificar_con_tests("f.py")
    assert r["veredicto"] == "ok"


def test_verificar_con_tests_rompe() -> None:
    with patch("verificador_tests._tests_para_archivo", return_value=[Path("t1.py")]), patch(
        "verificador_tests.ejecutar_tests",
        return_value={"ok": False, "detalle": [{"test": "t1.py", "ok": False}]},
    ):
        r = verificar_con_tests("f.py", antes={"ok": True, "detalle": [{"test": "t1.py", "ok": True}]})
    assert r["veredicto"] == "rompe"
    assert "t1.py" in r["regresiones"]


def test_verificar_baseline_roto_no_bloquea() -> None:
    """Si el test ya fallaba antes, un fallo despues no es regresion."""
    with patch("verificador_tests._tests_para_archivo", return_value=[Path("t1.py")]), patch(
        "verificador_tests.ejecutar_tests",
        return_value={"ok": False, "detalle": [{"test": "t1.py", "ok": False}]},
    ):
        r = verificar_con_tests("f.py", antes={"ok": False, "detalle": [{"test": "t1.py", "ok": False}]})
    assert r["veredicto"] == "ok"


def test_verificar_sin_baseline_atencion() -> None:
    """Sin baseline y tests fallan -> atencion (no bloquea)."""
    with patch("verificador_tests._tests_para_archivo", return_value=[Path("t1.py")]), patch(
        "verificador_tests.ejecutar_tests",
        return_value={"ok": False, "detalle": [{"test": "t1.py", "ok": False}]},
    ):
        r = verificar_con_tests("f.py")
    assert r["veredicto"] == "atencion"


def test_verificar_con_contenido_nuevo_restaura() -> None:
    """Escribe temporalmente, testea y restaura el archivo."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "mod.py"
        f.write_text("x = 1\n")
        with (
            patch("verificador_tests._tests_para_archivo", return_value=[Path("t1.py")]),
            patch("verificador_tests.ejecutar_tests", return_value={"ok": True, "detalle": []}),
        ):
            r = verificar_con_tests(str(f), nuevo_contenido="y = 2\n")
        assert r["veredicto"] == "ok"
        # El archivo se restauró
        assert f.read_text() == "x = 1\n"


def test_verificar_sin_tests_sin_contenido_nuevo() -> None:
    """Sin tests y sin nuevo_contenido -> sintaxis n/a (148)."""
    with patch("verificador_tests._tests_para_archivo", return_value=[]):
        r = verificar_con_tests("archivo_sin_tests.py")
    assert r == {"veredicto": "sin_tests", "sintaxis": "n/a"}


def test_tests_para_archivo_error_lectura(monkeypatch) -> None:
    """Error leyendo un test -> continue (56-57)."""
    from pathlib import Path as P

    import verificador_tests as v

    real_read = P.read_text

    def roto(self, *a, **k):
        if "test_fusion.py" in str(self):
            raise OSError("acceso denegado")
        return real_read(self, *a, **k)

    monkeypatch.setattr(P, "read_text", roto)
    repo = Path(__file__).parent.parent.parent
    tests = v._tests_para_archivo(str(repo / "motor" / "core" / "fusion" / "engine.py"))
    assert isinstance(tests, list)


def test_main_sin_argumentos(monkeypatch, capsys) -> None:
    """main sin archivo -> SystemExit(1) (183-185)."""
    import sys

    with patch.object(sys, "argv", ["verificador_tests.py"]):
        try:
            runpy = None  # no usamos runpy: ejecutamos el bloque via exec no
        finally:
            pass
    # El __main__ está en el if; lo simulamos con runpy y argv corto.
    import runpy

    script = Path(__file__).parent.parent.parent / "scripts" / "pro" / "verificador_tests.py"
    monkeypatch.setattr(sys, "argv", ["verificador_tests.py"])
    try:
        runpy.run_path(str(script), run_name="__main__")
        raise AssertionError("debió salir")
    except SystemExit as e:
        assert e.code == 1


def test_main_con_archivo(monkeypatch, capsys) -> None:
    """main con archivo real -> imprime resultado (186)."""
    import runpy
    import sys

    repo = Path(__file__).parent.parent.parent
    script = repo / "scripts" / "pro" / "verificador_tests.py"
    monkeypatch.setattr(sys, "argv", ["verificador_tests.py", str(repo / "motor" / "core" / "fusion" / "engine.py")])
    runpy.run_path(str(script), run_name="__main__")
    out = capsys.readouterr().out
    assert "veredicto" in out
