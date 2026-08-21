#!/usr/bin/env python3
"""contexto_rama.py — Conciencia de conexiones para el refactor (TASK-20260812-021).

Diseño RAMON ("conocimiento, pero con lógica"): el LLM no necesita todo el
árbol, solo la RAMA que está refactorizando — pero con conocimiento de
DE DÓNDE VIENE (quién llama a la función) y HACIA DÓNDE VA (qué llama ella).

Todo es determinista (AST + grep, sin LLM): el modelo recibe las conexiones
reales del código, no conocimiento general.

Estructura del contexto generado:
  DE DÓNDE VIENE:
    - llamadores dentro del archivo (AST)
    - llamadores en otros módulos del repo (grep de imports + llamadas)
    - imports del módulo que expone la función
  HACIA DÓNDE VA:
    - funciones que la función llama internamente (AST)
    - imports usados dentro de la función (AST)
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


def _imports_archivo(fuente: str) -> list[str]:
    """Imports del archivo (para saber qué nombres existen)."""
    try:
        tree = ast.parse(fuente)
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modulo = node.module or ""
            imports.extend(f"{modulo}.{a.name}" if modulo else a.name for a in node.names)
    return imports


def _llamadas_internas(func_source: str) -> list[str]:
    """Funciones que la función llama internamente (hacia dónde va)."""
    try:
        tree = ast.parse(func_source)
    except SyntaxError:
        return []
    llamadas: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                llamadas.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                llamadas.append(node.func.attr)
    return list(dict.fromkeys(llamadas))


def _llamadores_externos(repo: Path, func_name: str, modulo: str) -> list[str]:
    """Busca llamadores de la función en TODO el repo (de dónde viene).

    Determinista con grep: busca 'func_name(' en archivos .py, excluyendo
    el propio módulo y librerías externas.
    """
    if not repo.exists():
        return []
    excluir = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "site-packages",
        ".sandbox_packages",
        ".attic",
        ".tuneladora",
    }
    encontrados: list[str] = []
    patron = re.compile(rf"\b{re.escape(func_name)}\s*\(")
    for py in repo.rglob("*.py"):
        if any(x in py.parts for x in excluir):
            continue
        if modulo and modulo in str(py):
            continue  # ya cubierto por llamadores internos
        try:
            texto = py.read_text(errors="ignore")
        except OSError:
            continue
        if patron.search(texto):
            # Solo si importa el módulo de la función (conexión real)
            if modulo and f"import {modulo}" not in texto and f"from {modulo}" not in texto:
                continue
            encontrados.append(str(py.relative_to(repo)))
            if len(encontrados) >= 5:
                break
    return encontrados


def construir_contexto_rama(
    repo: Path,
    file_path: str,
    func_name: str,
    func_source: str,
    fuente_archivo: str = "",
) -> str:
    """Construye el contexto de la rama: de dónde viene y hacia dónde va.

    Returns:
        texto con las conexiones, listo para inyectar en el prompt.
    """
    if not fuente_archivo:
        try:
            fuente_archivo = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            fuente_archivo = ""

    partes: list[str] = []

    # DE DÓNDE VIENE: llamadores en el archivo
    if fuente_archivo:
        lineas = fuente_archivo.splitlines()
        llamadores_locales: list[str] = []
        try:
            tree = ast.parse(fuente_archivo)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == func_name
                    and node.lineno
                    and node.lineno <= len(lineas)
                ):
                    llamadores_locales.append(lineas[node.lineno - 1].strip())
        except SyntaxError:
            pass
        if llamadores_locales:
            unicos = list(dict.fromkeys(llamadores_locales))[:5]
            partes.append("LLAMADORES LOCALES (dentro del archivo):")
            partes.extend(f"  {c}" for c in unicos)

    # DE DÓNDE VIENE: llamadores externos en el repo
    modulo = ""
    if file_path:
        p = Path(file_path)
        # motor/core/fusion/engine.py -> motor.core.fusion.engine
        try:
            partes_rel = p.relative_to(repo).with_suffix("").parts
            modulo = ".".join(partes_rel)
        except ValueError:
            modulo = p.stem
    externos = _llamadores_externos(repo, func_name, modulo) if repo.exists() else []
    if externos:
        partes.append("LLAMADORES EXTERNOS (módulos que la usan):")
        partes.extend(f"  {e}" for e in externos)

    # HACIA DÓNDE VA: funciones que llama internamente
    internas = _llamadas_internas(func_source)
    if internas:
        partes.append("FUNCIONES QUE LLAMA INTERNAMENTE:")
        partes.append(f"  {', '.join(internas[:15])}")

    # HACIA DÓNDE VA: imports disponibles en el archivo
    if fuente_archivo:
        imports = _imports_archivo(fuente_archivo)
        if imports:
            partes.append("IMPORTS DISPONIBLES:")
            partes.append(f"  {', '.join(imports[:20])}")

    if not partes:
        return ""
    return "\n".join(partes)
