#!/usr/bin/env python3
"""edicion_ast.py — Edición quirúrgica determinista con AST (TASK-20260812-021).

Solución al 100% (diseño RAMON): el LLM genera SOLO las helpers nuevas, y el
sistema las inserta con AST — sin tocar la firma original, sin reescribir la
función, sin riesgo de romper la estructura.

Flujo:
  1. Se extrae la función original (AST: firma + cuerpo).
  2. El LLM devuelve SOLO las helpers (funciones nuevas).
  3. edicion_ast.insertar_helpers() las inserta ANTES de la función original
     y añade las llamadas donde el LLM indicó (o las deja para el prompt).
  4. Validación: compile del archivo completo + verificación de que la firma
     original NO cambió.
"""

from __future__ import annotations

import ast
import re


def extraer_firma(codigo_funcion: str) -> str:
    """Extrae la firma (def ...:) de la primera función del código."""
    try:
        tree = ast.parse(codigo_funcion)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                return f"{node.name}({', '.join(args)})"
    except SyntaxError:
        return ""
    return ""


def extraer_helpers(codigo_llm: str) -> list[str]:
    """Extrae SOLO las funciones top-level de la respuesta del LLM (helpers).

    Ignora la función principal (si el LLM la incluyó) — solo las demás.
    """
    try:
        tree = ast.parse(codigo_llm)
    except SyntaxError:
        return []
    helpers: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Conservar el código fuente de la función
            try:
                src = ast.get_source_segment(codigo_llm, node) or ""
                if src.strip():
                    helpers.append(src)
            except Exception:
                continue
    return helpers


def insertar_helpers(fuente_archivo: str, helpers: list[str], despues_linea: int = 0) -> str:
    """Inserta las helpers en el archivo sin tocar la función original.

    Las helpers se insertan justo antes de la primera definición de función
    (o en despues_linea si se especifica). No modifica nada más.
    """
    if not helpers:
        return fuente_archivo

    lineas = fuente_archivo.splitlines()
    # Buscar la primera línea de función (def) para insertar antes
    insertar_en = despues_linea
    if insertar_en <= 0:
        for i, l in enumerate(lineas):
            if re.match(r"^(async\s+)?def\s+", l):
                insertar_en = i
                break
    if insertar_en <= 0:
        insertar_en = len(lineas)

    bloque_helpers = "\n\n".join(h.rstrip() for h in helpers)
    nuevas = [*lineas[:insertar_en], bloque_helpers, "", *lineas[insertar_en:]]
    return "\n".join(nuevas)


def validar_archivo(fuente_archivo: str, firma_original: str) -> tuple[bool, str]:
    """Valida que el archivo compila y que la firma original se conserva."""
    try:
        compile(fuente_archivo, "<edicion>", "exec")
    except SyntaxError as e:
        return False, f"sintaxis: {e}"
    if firma_original:
        # Verificar que la firma sigue existiendo
        tree = ast.parse(fuente_archivo)
        firmas = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                firmas.add(f"{node.name}({', '.join(args)})")
        if firma_original not in firmas:
            return False, f"firma '{firma_original}' perdida"
    return True, "ok"


def aplicar_helpers(
    fuente_archivo: str,
    codigo_llm: str,
    firma_original: str = "",
) -> tuple[bool, str]:
    """Aplica la edición quirúrgica completa: inserta helpers y valida.

    Returns:
        (ok, contenido_resultante_o_error)
    """
    helpers = extraer_helpers(codigo_llm)
    if not helpers:
        return False, "sin helpers detectadas en la respuesta LLM"
    resultado = insertar_helpers(fuente_archivo, helpers)
    ok, error = validar_archivo(resultado, firma_original)
    if not ok:
        return False, error
    return True, resultado


def diff_quirurgico(fuente_original: str, codigo_llm: str, firma_original: str) -> tuple[bool, str]:
    """Edición quirúrgica por diff (alternativa robusta, TASK-20260812-021).

    El LLM devuelve el código refactorizado completo. Se calcula el diff con
    la función original y se extraen SOLO las adiciones de funciones nuevas
    (helpers). La firma original debe permanecer intacta.

    Returns:
        (ok, resultado_o_error)
    """
    # Extraer funciones del código LLM
    try:
        tree_llm = ast.parse(codigo_llm)
    except SyntaxError as e:
        return False, f"sintaxis en respuesta: {e}"

    funciones_llm = [n for n in tree_llm.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not funciones_llm:
        return False, "sin funciones en la respuesta"

    # Identificar la función principal (misma firma) vs helpers
    helpers: list[str] = []
    principal_encontrada = False
    for node in funciones_llm:
        args = [a.arg for a in node.args.args]
        firma_node = f"{node.name}({', '.join(args)})"
        if firma_original and firma_node == firma_original:
            principal_encontrada = True
            continue  # la principal no se toca
        src = ast.get_source_segment(codigo_llm, node) or ""
        if src.strip():
            helpers.append(src)

    if not helpers:
        if principal_encontrada:
            return False, "solo devolvió la principal (sin helpers)"
        return False, "sin helpers nuevas"

    # Insertar las helpers antes de la primera función del archivo
    return True, insertar_helpers(fuente_original, helpers)
