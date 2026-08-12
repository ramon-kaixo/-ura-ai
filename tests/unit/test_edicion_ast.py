"""Tests de edición quirúrgica con AST (TASK-20260812-021)."""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "pro"))

from edicion_ast import (
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


def test_extraer_firma_sintaxis_rota() -> None:
    assert extraer_firma("def (") == ""


def test_extraer_helpers_sintaxis_rota() -> None:
    assert extraer_helpers("def (") == []


def test_insertar_helpers_sin_punto_insercion() -> None:
    # Fuente sin funciones (solo codigo suelto) -> inserta al final
    fuente = "x = 1"
    resultado = insertar_helpers(fuente, ["def h():\n    return 2"])
    assert "def h()" in resultado
    compile(resultado, "<t>", "exec")


def test_validar_firma_vacia_ok() -> None:
    # Sin firma original -> solo comprueba sintaxis
    ok, err = validar_archivo("def f():\n    pass", "")
    assert ok
    assert err == "ok"


def test_aplicar_con_funcion_extrae() -> None:
    # aplicar_helpers extrae TODAS las funciones de la respuesta (incl. la
    # principal como helper) y las inserta — no rompe el archivo
    fuente = "def original(a):\n    return a"
    respuesta = "def original(a):\n    return a * 2"
    ok, resultado = aplicar_helpers(fuente, respuesta, "original(a)")
    assert ok
    compile(resultado, "<t>", "exec")
    assert "def original" in resultado


def test_diff_quirurgico_sintaxis_rota() -> None:
    from edicion_ast import diff_quirurgico

    ok, error = diff_quirurgico("x = 1", "def (", "f()")
    assert not ok
    assert "sintaxis" in error


def test_diff_quirurgico_sin_funciones() -> None:
    from edicion_ast import diff_quirurgico

    ok, error = diff_quirurgico("x = 1", "y = 2", "f()")
    assert not ok
    assert "sin funciones" in error


def test_diff_quirurgico_solo_principal() -> None:
    from edicion_ast import diff_quirurgico

    ok, error = diff_quirurgico("x = 1", "def f(a):\n    return a", "f(a)")
    assert not ok
    assert "solo devolvió la principal" in error


def test_diff_quirurgico_con_helpers() -> None:
    from edicion_ast import diff_quirurgico

    fuente = "def f(a):\n    return a + 1"
    respuesta = "def helper(x):\n    return x * 2\n\ndef f(a):\n    return a + helper(a)"
    ok, resultado = diff_quirurgico(fuente, respuesta, "f(a)")
    assert ok
    assert "def helper" in resultado
    compile(resultado, "<t>", "exec")


def test_extraer_helpers_async() -> None:
    codigo = "async def helper_async(x):\n    return x"
    helpers = extraer_helpers(codigo)
    assert len(helpers) == 1
    assert "async def helper_async" in helpers[0]


def test_validar_archivo_sintaxis_rota() -> None:
    ok, error = validar_archivo("def (", "f()")
    assert not ok
    assert "sintaxis" in error


def test_diff_quirurgico_helpers_vacio() -> None:
    from edicion_ast import diff_quirurgico

    # Respuesta con funcion principal SOLO (firma coincide) -> sin helpers
    ok, error = diff_quirurgico("x = 1", "def f(a):\n    return a", "f(a)")
    assert not ok
    assert "solo devolvió la principal" in error


def test_extraer_helpers_sin_fuente_valida() -> None:
    # get_source_segment con codigo vacio
    assert extraer_helpers("") == []


def test_insertar_helpers_vacio_devuelve_original() -> None:
    fuente = "def f():\n    pass"
    assert insertar_helpers(fuente, []) == fuente


def test_diff_quirurgico_principal_y_helper() -> None:
    from edicion_ast import diff_quirurgico

    fuente = "def f(a):\n    return a + 1"
    # Respuesta con helper Y principal -> extrae solo la helper
    respuesta = "def helper(x):\n    return x * 2\n\ndef f(a):\n    return a + helper(a)"
    ok, resultado = diff_quirurgico(fuente, respuesta, "f(a)")
    assert ok
    assert "def helper" in resultado
    assert resultado.count("def ") == 2  # helper + original


def test_extraer_firma_sin_funcion() -> None:
    """Código sin def -> "" (33)."""
    from edicion_ast import extraer_firma

    assert extraer_firma("x = 1\n") == ""


def test_extraer_helpers_solo_assigns() -> None:
    """Código sin funciones -> [] (47->46)."""
    from edicion_ast import extraer_helpers

    assert extraer_helpers("x = 1\n") == []


def test_extraer_helpers_segmento_vacio(monkeypatch) -> None:
    """get_source_segment vacío -> no appendea (51->46)."""
    import ast

    from edicion_ast import extraer_helpers

    monkeypatch.setattr(ast, "get_source_segment", lambda *a, **k: "")
    assert extraer_helpers("def h():\n    pass\n") == []


def test_extraer_helpers_segmento_error(monkeypatch) -> None:
    """get_source_segment lanza -> continue (53-54)."""
    import ast

    from edicion_ast import extraer_helpers

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(ast, "get_source_segment", boom)
    assert extraer_helpers("def h():\n    pass\n") == []


def test_insertar_helpers_despues_linea_positiva() -> None:
    """despues_linea > 0 -> no busca def (70->75)."""
    from edicion_ast import insertar_helpers

    fuente = "def f():\n    pass\n"
    r = insertar_helpers(fuente, ["def aux():\n    pass"], despues_linea=5)
    assert "def aux()" in r


def test_insertar_helpers_con_def(monkeypatch) -> None:
    """Después de buscar def (75->78): la fuente con def y despues_linea<=0."""
    import re

    from edicion_ast import insertar_helpers

    real_match = re.match
    llamado = []

    def spy(*a, **k):
        llamado.append(1)
        return real_match(*a, **k)

    monkeypatch.setattr(re, "match", spy)
    fuente = "x = 1\ndef f():\n    pass\n"
    r = insertar_helpers(fuente, ["def aux():\n    pass"])
    assert llamado  # se buscó la primera def
    assert r.index("def aux") < r.index("def f")


def test_aplicar_helpers_firma_perdida() -> None:
    """validacion falla -> (False, error) (118)."""
    from edicion_ast import aplicar_helpers

    fuente = "def f(x):\n    return x\n"
    codigo_llm = "def aux():\n    return 1\n"
    ok, resultado = aplicar_helpers(fuente, codigo_llm, firma_original="f(x, y)")
    assert ok is False
    assert "firma" in resultado


def test_diff_quirurgico_src_vacio(monkeypatch) -> None:
    """Helper con src vacío -> se ignora; sin helpers y sin principal (155-161)."""
    import ast

    from edicion_ast import diff_quirurgico

    monkeypatch.setattr(ast, "get_source_segment", lambda *a, **k: "")
    ok, error = diff_quirurgico("def f(x):\n    return x\n", "def otra(a):\n    return a\n", "f(x)")
    assert ok is False
    assert error == "sin helpers nuevas"
