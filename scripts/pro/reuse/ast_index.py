"""AST Index — extrae firmas de funciones y clases del código fuente.

Para cada función/clase extrae:
  - nombre
  - archivo
  - línea
  - parámetros
  - decoradores
  - docstring
  - hash del body AST
  - imports del archivo
"""

from __future__ import annotations

import ast
import hashlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def index_file(filepath: Path) -> list[dict[str, Any]]:
    """Indexa un archivo Python. Retorna lista de funciones/clases encontradas."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    entries: list[dict[str, Any]] = []
    file_imports = _extract_imports(tree)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entries.append(_extract_function(node, filepath, file_imports))
        elif isinstance(node, ast.ClassDef):
            entries.append(_extract_class(node, filepath, file_imports))
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    entries.append(_extract_function(item, filepath, file_imports, cls=node.name))
    return entries


def _extract_imports(tree: ast.AST) -> list[str]:
    imports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _body_hash(node: ast.AST) -> str:
    h = hashlib.sha256()
    for child in ast.iter_child_nodes(node):
        h.update(str(type(child).__name__).encode())
    return h.hexdigest()[:12]


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    filepath: Path,
    file_imports: list[str],
    cls: str = "",
) -> dict[str, Any]:
    params = [arg.arg for arg in node.args.args]
    decorators = [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
    docstring = ast.get_docstring(node) or ""
    body_hash = _body_hash(node)
    calls = _extract_calls(node)
    name = f"{cls}.{node.name}" if cls else node.name
    return {
        "type": "function",
        "name": name,
        "file": str(filepath.relative_to(filepath.parent.parent) if filepath.parent.parent else filepath),
        "line": node.lineno,
        "params": params,
        "param_count": len(params),
        "decorators": decorators,
        "docstring_preview": docstring[:100],
        "body_hash": body_hash,
        "calls": calls[:5],
        "imports": file_imports[:5],
    }


def _extract_class(
    node: ast.ClassDef,
    filepath: Path,
    file_imports: list[str],
) -> dict[str, Any]:
    docstring = ast.get_docstring(node) or ""
    methods = [n.name for n in ast.iter_child_nodes(node) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return {
        "type": "class",
        "name": node.name,
        "file": str(filepath.relative_to(filepath.parent.parent) if filepath.parent.parent else filepath),
        "line": node.lineno,
        "methods": methods,
        "method_count": len(methods),
        "docstring_preview": docstring[:100],
    }


def _extract_calls(node: ast.AST) -> list[str]:
    calls = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            calls.append(n.func.attr)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            calls.append(n.func.id)
    return calls
