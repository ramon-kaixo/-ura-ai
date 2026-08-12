"""Tests de edición quirúrgica con AST (TASK-20260812-021)."""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "pro"))

from edicion_ast import (  # noqa: E402
    aplicar_helpers,
    extraer_firma,
    extraer_helpers,
    insertar_helpers,
    validar_archivo,
)


def test_extraer_firma() -> None:
    firma = extraer_firma("def procesar(datos, limite=10):\n    return datos")
    assert firma == "procesar(datos, limite)"


def test_extraer_helpers_solo_helpers() -> None:
    codigo = """def helper1(x):
    return x * 2


def helper2(y):
    return y + 1


def funcion_principal(z):
    return helper1(z) + helper2(z)"""
    helpers = extraer_helpers(codigo)
    # Debe extraer las 3 (sin distinguir principal — el prompt debe pedir solo helpers)
    assert len(helpers) == 3


def test_insertar_helpers_no_rompe() -> None:
    fuente = """def original(a, b):
    return a + b"""
    helpers = ["def nuevo_helper(x):\n    return x * 2"]
    resultado = insertar_helpers(fuente, helpers)
    compile(resultado, "<t>", "exec")  # no debe lanzar
    assert "def nuevo_helper" in resultado
    assert "def original" in resultado


def test_validar_firma_preservada() -> None:
    fuente = """def original(a, b):
    return a + b"""
    ok, err = validar_archivo(fuente, "original(a, b)")
    assert ok, err


def test_validar_firma_perdida() -> None:
    fuente = """def otra(x):
    return x"""
    ok, _ = validar_archivo(fuente, "original(a, b)")
    assert not ok


def test_aplicar_helpers_completo() -> None:
    fuente = """def original(a, b):
    return a + b"""
    respuesta_llm = """def helper_suma(x, y):
    \"\"\"Suma dos valores.\"\"\"
    return x + y"""
    ok, resultado = aplicar_helpers(fuente, respuesta_llm, "original(a, b)")
    assert ok
    # El archivo resultante compila y conserva ambas funciones
    tree = ast.parse(resultado)
    nombres = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "original" in nombres
    assert "helper_suma" in nombres


def test_aplicar_sin_helpers_rechaza() -> None:
    fuente = "def original(a, b):\n    return a + b"
    ok, error = aplicar_helpers(fuente, "no hay funciones aqui", "original(a, b)")
    assert not ok
    assert "sin helpers" in error
