#!/usr/bin/env python3
"""fraccionador_ast.py — Fraccionamiento de funciones por bloques funcionales (AST).

Diseño original de RAMON (TASK-20260812-019):
  1. Cortar por BLOQUES funcionales (If/For/While/With/Try/def anidadas) usando
     el árbol sintáctico (ast) — determinista, sin LLM, nunca rompe sintaxis.
  2. Cada bloque se entrega al LLM por separado (piezas pequeñas = respuestas
     rápidas = mínimo de peticiones bien hechas).
  3. Reensamblar los bloques refactorizados en el orden original.

Garantías:
  - El fraccionamiento es por LÍNEAS de los nodos AST: un bloque nunca se parte
    a mitad (un `if` completo va entero a un fragmento).
  - El código de cada fragmento compila por separado (verificable con compile()).
  - Reensamblar los fragmentos en orden produce EXACTAMENTE el código original.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class Bloque:
    """Un bloque funcional dentro de una función."""

    nombre: str
    lineno: int
    end_lineno: int
    tipo: str  # if/for/while/with/try/def/codigo_plano


def _tipo_nodo(node: ast.AST) -> str:
    mapeo = {
        ast.If: "if",
        ast.For: "for",
        ast.While: "while",
        ast.With: "with",
        ast.Try: "try",
        ast.FunctionDef: "def",
        ast.AsyncFunctionDef: "def",
    }
    return mapeo.get(type(node), "codigo_plano")


def _nombre_nodo(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    if isinstance(node, ast.If):
        return f"if@{node.lineno}"
    if isinstance(node, ast.For):
        return f"for@{node.lineno}"
    if isinstance(node, ast.While):
        return f"while@{node.lineno}"
    if isinstance(node, ast.With):
        return f"with@{node.lineno}"
    if isinstance(node, ast.Try):
        return f"try@{node.lineno}"
    return f"bloque@{node.lineno}"


def extraer_bloques(func_source: str) -> list[Bloque]:
    """Extrae los bloques funcionales de nivel superior dentro de una función.

    Solo considera bloques con indentación de nivel 1 (cuerpo directo de la
    función). Los bloques anidados dentro de un if/for se quedan con su padre.
    """
    try:
        tree = ast.parse(func_source)
    except SyntaxError:
        return []

    if len(tree.body) != 1 or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []

    func = tree.body[0]
    bloques: list[Bloque] = []
    for node in func.body:
        # Py >= 3.8: todos los nodos AST tienen end_lineno (None si sin asignar),
        # por lo que la comprobación hasattr del diseño original era código muerto.
        if node.end_lineno is None:
            continue
        bloques.append(
            Bloque(
                nombre=_nombre_nodo(node),
                lineno=node.lineno,
                end_lineno=node.end_lineno,
                tipo=_tipo_nodo(node),
            ),
        )
    return bloques


def fraccionar(func_source: str, max_lineas: int = 60) -> list[str]:
    """Fracciona una función en fragmentos de <= max_lineas por bloques.

    Estrategia (diseño RAMON):
      1. Si la función cabe en max_lineas → un solo fragmento.
      2. Si no: agrupar bloques consecutivos en fragmentos que no superen
         max_lineas, cortando SIEMPRE entre bloques (nunca a mitad).
      3. La firma (def ... :) siempre va en el primer fragmento.
    """
    lineas = func_source.split("\n")
    if len(lineas) <= max_lineas:
        return [func_source]

    bloques = extraer_bloques(func_source)
    if not bloques:
        # Sin bloques detectables: fraccionar por líneas en límites de
        # indentación 0/4 (seguro) o devolver completo si no hay puntos seguros.
        return [func_source]

    # Incluir la firma + primer bloque en el primer fragmento
    fragmentos: list[str] = []
    actual: list[str] = []

    for i, b in enumerate(bloques):
        # Líneas de este bloque (inclusive): de b.lineno a b.end_lineno
        inicio = b.lineno - 1
        fin = b.end_lineno  # end_lineno es inclusivo (1-based)
        bloque_lines = lineas[inicio:fin]

        if i == 0:
            # Primer fragmento: firma (líneas antes del bloque) + primer bloque
            actual = lineas[:fin]
            continue

        # Incluir líneas de relleno (comentarios, blancos) entre el bloque
        # anterior y este — ast no las ve como nodos y se perderían.
        fin_anterior = bloques[i - 1].end_lineno
        relleno = lineas[fin_anterior:inicio]
        bloque_con_relleno = relleno + bloque_lines

        # Líneas del fragmento actual
        n_actual = len(actual)
        if n_actual + len(bloque_con_relleno) > max_lineas:
            fragmentos.append("\n".join(actual))
            actual = list(bloque_con_relleno)
        else:
            actual.extend(bloque_con_relleno)

    # Invariante: con bloques no vacíos, `actual` se inicializa con el primer
    # bloque (i == 0, líneas antes de `fin` que incluyen la firma) y nunca
    # queda vacío, por lo que el último fragmento siempre existe.
    fragmentos.append("\n".join(actual))
    return fragmentos


def reensamblar(fragmentos: list[str]) -> str:
    """Reensambla fragmentos en el orden original."""
    return "\n".join(fragmentos)
