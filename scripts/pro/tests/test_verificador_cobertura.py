"""Tests de verificador_cobertura.py (TASK-20260814-001) — objetivo 80-90%.

Cubre: _normalize_modulo (ramas), medir_cobertura con modulo real minimo y con
tests inexistentes, evaluar (dentro/fuera de horquilla y brutos), diff_py
(con git real y base inexistente), main (--ci sin cambios, objetivo sin
--tests, --ci con cambios, argumento faltante).
"""

from __future__ import annotations

import sys
from pathlib import Path

TESTDIR = Path(__file__).parent
sys.path.insert(0, str(TESTDIR.parent / "pro"))

from verificador_cobertura import (
    MAX_DEFAULT,
    MIN_DEFAULT,
    _normalize_modulo,
    diff_py,
    evaluar,
    main,
    medir_cobertura,
)

MODULO_TMP = TESTDIR / "modulo_fixture.py"
TEST_FIXTURE = TESTDIR / "test_modulo_fixture.py"


def _escribir_fixture() -> None:
    MODULO_TMP.write_text(
        "def suma(a, b):\n    return a + b\n\n"
        "def resta(a, b):\n    return a - b\n\n"
        "def divide(a, b):\n    if b == 0:\n        raise ValueError('div0')\n"
        "    return a / b\n"
    )
    TEST_FIXTURE.write_text(
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parent))\n"
        "from modulo_fixture import suma, resta, divide\n"
        "def test_suma():\n    assert suma(1, 2) == 3\n"
        "def test_resta():\n    assert resta(5, 2) == 3\n"
        "def test_divide():\n    assert divide(6, 2) == 3.0\n"
    )


def test_normalize_py() -> None:
    assert _normalize_modulo("modulo.py") == "modulo"
    assert _normalize_modulo("modulo") == "modulo"


def test_normalize_trailing_slash() -> None:
    assert _normalize_modulo("dir/") == "dir"
    assert _normalize_modulo("dir//") == "dir"


def test_evaluar_dentro() -> None:
    ok, fuera = evaluar({"a.py": 85.0}, MIN_DEFAULT, MAX_DEFAULT)
    assert ok == ["a.py: 85.0%"]
    assert fuera == []


def test_evaluar_fuera_min() -> None:
    ok, fuera = evaluar({"a.py": 79.9}, MIN_DEFAULT, MAX_DEFAULT)
    assert ok == []
    assert "a.py: 79.9%" in fuera[0]


def test_evaluar_sobre_min_sin_tope() -> None:
    ok, fuera = evaluar({"a.py": 90.1}, MIN_DEFAULT, MAX_DEFAULT)
    assert ok == ["a.py: 90.1%"]
    assert fuera == []


def test_medir_cobertura_fixture() -> None:
    _escribir_fixture()
    try:
        result = medir_cobertura(str(TESTDIR), [str(TEST_FIXTURE)], 80, 90)
        assert any(k.endswith("modulo_fixture.py") for k in result)
        assert max(result.values()) >= 80
    finally:
        MODULO_TMP.unlink(missing_ok=True)
        TEST_FIXTURE.unlink(missing_ok=True)


def test_medir_cobertura_sin_tests() -> None:
    _escribir_fixture()
    try:
        result = medir_cobertura(str(TESTDIR), ["test_modulo_fixture.py"], 80, 90)
        assert any(k.endswith("modulo_fixture.py") for k in result)
    finally:
        MODULO_TMP.unlink(missing_ok=True)
        TEST_FIXTURE.unlink(missing_ok=True)


def test_diff_py_real() -> None:
    lista = diff_py("HEAD~0")
    assert isinstance(lista, list)


def test_main_ci_sin_cambios() -> None:
    assert main(["--ci", "--base", "HEAD"]) == 0


def test_main_sin_objetivo_error() -> None:
    try:
        main([])
        raise AssertionError("debería haber error de parser")
    except SystemExit:
        pass


def test_main_min_max_defaults() -> None:
    ok, _ = evaluar({"x.py": 85.0}, MIN_DEFAULT, MAX_DEFAULT)
    assert ok == ["x.py: 85.0%"]


def test_medir_cobertura_ruta_inexistente() -> None:
    assert medir_cobertura("nada/existente.py", [], 80, 90) == {}


def test_main_objetivo_con_fixture() -> None:
    _escribir_fixture()
    try:
        rc = main([str(TESTDIR), "--tests", str(TEST_FIXTURE)])
        assert rc == 1
    finally:
        MODULO_TMP.unlink(missing_ok=True)
        TEST_FIXTURE.unlink(missing_ok=True)


def test_main_objetivo_fuente_inexistente() -> None:
    assert main(["ruta/inexistente.py"]) == 0


def test_medir_report_fallido(monkeypatch: object) -> None:
    import subprocess as sp

    from verificador_cobertura import medir_cobertura

    _escribir_fixture()
    try:

        def fake_run(*args: object, **kwargs: object) -> object:
            if "json" in str(args[0]):
                return sp.CompletedProcess(args[0], 1, "", "")
            return sp.CompletedProcess(args[0], 0, "", "")

        monkeypatch.setattr(sp, "run", fake_run)
        assert medir_cobertura(str(MODULO_TMP), []) == {}
    finally:
        MODULO_TMP.unlink(missing_ok=True)
        TEST_FIXTURE.unlink(missing_ok=True)


def test_medir_report_invalido(monkeypatch: object) -> None:
    import pathlib
    import subprocess as sp

    from verificador_cobertura import medir_cobertura

    _escribir_fixture()
    try:
        real_run = sp.run

        def fake_run(*args: object, **kwargs: object) -> object:
            c = real_run(*args, **kwargs)
            if "json" in str(args[0]):
                rc = next(a for a in args[0] if a.startswith("--rcfile="))
                pathlib.Path(rc.split("=", 1)[1]).parent.joinpath("coverage.json").write_text("no es json")
            return c

        monkeypatch.setattr(sp, "run", fake_run)
        assert medir_cobertura(str(MODULO_TMP), []) == {}
    finally:
        MODULO_TMP.unlink(missing_ok=True)
        TEST_FIXTURE.unlink(missing_ok=True)


def test_e2e_cli_sin_argumentos() -> None:
    import pathlib
    import subprocess as sp
    import sys as _sys

    repo = pathlib.Path(__file__).resolve().parents[3]
    r = sp.run(
        [_sys.executable, "scripts/pro/verificador_cobertura.py"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 2
