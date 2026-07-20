#!/usr/bin/env python3
# PLUGIN METADATA
PLUGIN = {
    "name": "poda_mecanica",
    "phase": "refactor",
    "timeout": 30,
    "args": ["--json"],
    "blocking": False,
    "needs_file": False,
}
"""Poda Mecánica + Anclaje Cromático — Fase 0 del Pipeline.

Corta código muerto (CPU, milisegundos) y genera mapa cromático 🔴🟢
para que el LLM solo reciba lógica pura y la Compactadora pueda
reconstruir sin riesgo de deriva.

Flujo:
  [Archivo] → Poda Mecánica (ruff F841/F401 + strip comentarios)
           → Código limpio (-10-20% tokens)
           → Anclaje Cromático (AST → 🔴🟢)
           → metadata.json + codigo_limpio.py

Uso:
  python3 poda_mecanica.py <archivo> [--output <dir>] [--json]
"""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def buscar_ruff() -> str | None:
    """Busca ruff en ubicaciones conocidas."""
    for c in [
        shutil.which("ruff"),
        "/home/ramon/URA/ura_ia_1972/.venv/bin/ruff",
        Path("~/.local/bin/ruff").expanduser(),
        "/usr/local/bin/ruff",
    ]:
        if c and Path(c).is_file():
            return c
    return None


def eliminar_comentarios_no_docstring(codigo: str) -> tuple[str, int]:
    """Elimina comentarios de línea (#) que NO sean parte de docstrings.

    Returns:
        (codigo_limpio, lineas_eliminadas)

    """
    lineas = codigo.splitlines()
    resultado = []
    eliminadas = 0
    en_docstring = False
    en_docstring_simple = False

    for linea in lineas:
        stripped = linea.strip()

        # Detectar entrada/salida de docstrings
        if stripped.startswith(('"""', "'''")):
            if en_docstring:
                en_docstring = False
            elif stripped.count('"""') == 2 or stripped.count("'''") == 2:
                pass  # docstring inline
            else:
                en_docstring = True
            resultado.append(linea)
            continue

        if en_docstring:
            resultado.append(linea)
            continue

        # Detectar entrada/salida de docstrings con comillas simples
        if stripped.startswith("'") and stripped.endswith("'") and len(stripped) > 3:
            if stripped.count("'") >= 3:
                en_docstring_simple = not en_docstring_simple
            resultado.append(linea)
            continue

        if en_docstring_simple:
            resultado.append(linea)
            continue

        # Comentarios de línea — solo eliminar inline (tras código)
        idx = _encontrar_comentario(linea)
        if idx is not None:
            prefix = linea[:idx].strip()
            if prefix:  # tiene código antes del comentario → eliminar solo el comentario
                resultado.append(linea[:idx].rstrip())
                eliminadas += 1
                continue
            # Si es línea de solo comentario, mantenerla (podría ser el único cuerpo de un bloque)
            resultado.append(linea)

        resultado.append(linea)

    return "\n".join(resultado), eliminadas


def _encontrar_comentario(linea: str) -> int | None:
    """Encuentra la posición del primer # que NO esté dentro de una cadena."""
    en_cadena = None
    i = 0
    while i < len(linea):
        ch = linea[i]
        if en_cadena:
            if ch == "\\":
                i += 2
                continue
            if ch == en_cadena:
                en_cadena = None
        elif ch in ('"', "'"):
            en_cadena = ch
        elif ch == "#":
            return i
        i += 1
    return None


def poda_mecanica(ruta: Path) -> tuple[str, int, int, int]:
    """Ejecuta la poda completa: ruff F841/F401/F811 + strip comentarios.

    Returns:
        (codigo_podado, chars_original, chars_podado, lineas_comentarios)

    """
    codigo_original = ruta.read_text(encoding="utf-8")
    chars_original = len(codigo_original)

    # 1. Ruff fix
    ruff_bin = buscar_ruff()
    if ruff_bin:
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".py")
            os.close(fd)
            with open(tmp_path, "w") as f:  # noqa: PTH123
                f.write(codigo_original)

            subprocess.run(
                [ruff_bin, "check", "--fix", "--select", "F841,F401,F811", tmp_path],
                capture_output=True,
                timeout=15,
                check=False,
            )
            codigo_post_ruff = Path(tmp_path).read_text(encoding="utf-8")
            os.unlink(tmp_path)  # noqa: PTH108
        except Exception:
            codigo_post_ruff = codigo_original
    else:
        codigo_post_ruff = codigo_original

    # 2. Strip comentarios no-docstring
    codigo_podado, lineas_eliminadas = eliminar_comentarios_no_docstring(codigo_post_ruff)

    chars_podado = len(codigo_podado)

    return codigo_podado, chars_original, chars_podado, lineas_eliminadas


def anclaje_cromatico(codigo: str) -> dict:
    """Genera mapa cromático 🔴🟢 del código limpio.

    🔴 Roja: end_line de cada instrucción lógica (función, clase, asignación)
    🟢 Verde: gaps entre bloques (líneas en blanco, indentación)

    Returns:
        Dict con el mapa cromático.

    """
    lineas = codigo.splitlines()
    total_lineas = len(lineas)
    rojas = []
    verdes = []

    try:
        arbol = ast.parse(codigo)
    except SyntaxError:
        # Si no compila, estimar por líneas no vacías
        for i, linea in enumerate(lineas, 1):
            if linea.strip() and not linea.strip().startswith("#"):
                rojas.append(i)
        return {
            "tipo": "fallback_syntax",
            "total_rojas": len(rojas),
            "total_verdes": 0,
            "rojas": rojas[:100],  # límite 100 para no explotar JSON
            "verdes": [],
            "total_lineas": total_lineas,
        }

    # 🔴 Rojas de funciones y clases
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):  # noqa: SIM102
            if hasattr(nodo, "end_lineno") and nodo.end_lineno:
                rojas.append(nodo.end_lineno)
        if isinstance(nodo, (ast.For, ast.While, ast.If, ast.Try, ast.With)):
            # Bloques de control: su último body
            for body_node in getattr(nodo, "body", []):
                if hasattr(body_node, "end_lineno") and body_node.end_lineno:
                    rojas.append(body_node.end_lineno)  # noqa: PERF401
            for body_node in getattr(nodo, "orelse", []):
                if hasattr(body_node, "end_lineno") and body_node.end_lineno:
                    rojas.append(body_node.end_lineno)  # noqa: PERF401

    # 🟢 Verdes: líneas en blanco entre bloques (PEP 8)
    for i, linea in enumerate(lineas, 1):
        if i > 0 and i <= total_lineas:
            idx = i - 1
            if not linea.strip() and idx > 0:  # noqa: SIM102
                # Línea en blanco
                if idx + 1 < total_lineas and lineas[idx + 1].strip():
                    # Entre código → es gap estructural
                    verdes.append(i)

    # Añadir gaps entre funciones (PEP 8: 2 blank lines)
    for i in range(1, total_lineas - 1):
        if not lineas[i].strip() and not lineas[i - 1].strip() and i + 1 < total_lineas and lineas[i + 1].strip():
            verdes.append(i + 1)  # noqa: PERF401

    rojas = sorted(set(rojas))
    verdes = sorted(set(verdes))

    return {
        "tipo": "chromatic_map",
        "total_rojas": len(rojas),
        "total_verdes": len(verdes),
        "rojas": rojas[:100],
        "verdes": verdes[:50],
        "total_lineas": total_lineas,
    }


def pipeline_poda(ruta: Path, output_dir: Path | None = None) -> dict:
    """Ejecuta Poda Mecánica + Anclaje Cromático y guarda resultados.

    Returns:
        Dict con resultados completos.

    """
    # 1. Poda
    codigo_podado, chars_original, chars_podado, comentarios_elim = poda_mecanica(ruta)
    tokens_original = chars_original // 4
    tokens_podado = chars_podado // 4
    pct_ahorro = round((1 - chars_podado / max(chars_original, 1)) * 100, 1)

    # 2. Anclaje Cromático
    mapa = anclaje_cromatico(codigo_podado)

    # 3. Guardar resultados
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        nombre_base = ruta.stem

        # Código limpio
        (output_dir / f"{nombre_base}_limpiado.py").write_text(codigo_podado, encoding="utf-8")

        # Metadata
        metadata = {
            "archivo_original": str(ruta),
            "chars_original": chars_original,
            "chars_podado": chars_podado,
            "tokens_original": tokens_original,
            "tokens_podado": tokens_podado,
            "ahorro_pct": pct_ahorro,
            "comentarios_eliminados": comentarios_elim,
            "mapa_cromatico": mapa,
        }
        ruta_meta = output_dir / f"{nombre_base}_chromatic.json"
        ruta_meta.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    return {
        "status": "OK",
        "archivo": str(ruta),
        "chars_original": chars_original,
        "chars_podado": chars_podado,
        "ahorro_pct": pct_ahorro,
        "tokens_original": tokens_original,
        "tokens_podado": tokens_podado,
        "comentarios_eliminados": comentarios_elim,
        "mapa_cromatico": {
            "total_rojas": mapa["total_rojas"],
            "total_verdes": mapa["total_verdes"],
            "total_lineas": mapa["total_lineas"],
        },
    }


def scan_project() -> None:
    """Escanear todo el proyecto."""
    from pathlib import Path

    URA_ROOT = Path("/home/ramon/URA/ura_ia_1972")
    results = {}
    for py_file in URA_ROOT.rglob("*.py"):
        p = str(py_file)
        if any(
            x in p
            for x in ["/.venv/", "/.git/", "/__pycache__/", "/backups/", "/site-packages/", "/scripts_eliminados/"]
        ):
            continue
        try:
            content = py_file.read_text()
            lines = content.splitlines()
            dead = sum(1 for l in lines if l.strip().startswith("# ") and "TODO" not in l)
            results[p] = {"dead_comments": dead, "total_lines": len(lines)}
        except Exception:  # noqa: S110
            pass


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Poda Mecánica + Anclaje Cromático")
    parser.add_argument("archivo", nargs="?", default=None, help="Archivo .py a procesar")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--output", "-o", help="Directorio de salida (guarda código limpio + metadata)")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    ruta = Path(args.archivo)
    if not ruta.exists():
        sys.exit(1)

    pipeline_poda(ruta, Path(args.output) if args.output else None)

    if args.json or args.output:
        pass


if __name__ == "__main__":
    main()
