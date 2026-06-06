#!/usr/bin/env python3
"""Compactadora Determinista — Reintegra código refactorizado.

Principios:
  1. CONTABILIDAD: cada línea entrante = línea saliente.
     Si entran 300 líneas y salen 320, hay 20 líginas que justificar.
  2. VERIFICACIÓN: AST válido, tokens coherentes, mapa cromático.
  3. DRY-RUN: validación sin escritura.
"""

PLUGIN = {
    "name": "compactadora",
    "phase": "refactor",
    "timeout": 60,
    "blocking": False,
    "needs_file": False,
}

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path


def parse_metadata(ruta: Path) -> dict:
    """Lee el metadata generado por el Fragmentador."""
    return json.loads(ruta.read_text())


def extraer_chincheta(codigo: str) -> tuple[int, int, str]:
    """Extrae la chincheta única del código original vía AST.

    Returns:
        (start_line, end_line, nombre_funcion)

    """
    tree = ast.parse(codigo)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return (node.lineno, node.end_lineno, node.name)
    msg = "No se encontró ninguna función/clase en el código"
    raise ValueError(msg)


def validar_contabilidad(
    metadata: dict,
    codigo_original: str,
    codigo_nuevo: str,
    tolerancia: float = 0.10,
) -> tuple[bool, dict]:
    """Verifica que la contabilidad de tokens cuadre.

    tokens_esperados = tokens_in - tokens_removed + tokens_added
    """
    tokens_in = len(codigo_original.split())
    tokens_out = len(codigo_nuevo.split())

    removed = metadata.get("tokens_removed", 0)
    added = metadata.get("tokens_added", 0)

    esperado = tokens_in - removed + added
    diff = abs(tokens_out - esperado)
    diff_pct = diff / max(esperado, 1)

    ok = diff_pct <= tolerancia

    reporte = {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_removed_esperado": removed,
        "tokens_added_esperado": added,
        "tokens_esperado": esperado,
        "diferencia": diff,
        "diferencia_pct": round(diff_pct * 100, 1),
        "dentro_tolerancia": ok,
    }
    return ok, reporte


def inyeccion_quirurgica(
    original: str,
    start_line: int,
    end_line: int,
    nuevo_codigo: str,
) -> str:
    """Reemplazo quirúrgico: backward splicing desde la chincheta.

    Args:
        original: Código fuente completo.
        start_line: Línea de inicio de la función (1-indexed).
        end_line: Línea de fin de la función (1-indexed) — la chincheta.
        nuevo_codigo: Código refactorizado.

    Returns:
        Código completo con la función reemplazada.

    """
    lines = original.splitlines()
    nuevo_lines = nuevo_codigo.splitlines()

    if start_line < 1 or end_line > len(lines):
        msg = f"Líneas fuera de rango: {start_line}-{end_line} vs {len(lines)} líneas"
        raise ValueError(msg)

    resultado = lines[: start_line - 1] + nuevo_lines + lines[end_line:]
    return "\n".join(resultado)


def verificar_compile(codigo: str, nombre: str = "<string>") -> tuple[bool, str | None]:
    """Verifica que el código compile sin errores."""
    try:
        compile(codigo, nombre, "exec")
        return True, None
    except SyntaxError as e:
        return False, str(e)


def verificar_firma_ast(codigo_original: str, codigo_final: str) -> tuple[bool, list[str]]:
    """Verifica que las firmas de funciones se mantengan (AST Diff)."""
    try:
        tree_orig = ast.parse(codigo_original)
        tree_final = ast.parse(codigo_final)
    except SyntaxError:
        return False, ["Error de sintaxis en uno de los códigos"]

    firmas_orig = set()
    firmas_final = set()

    for node in ast.walk(tree_orig):
        if isinstance(node, ast.FunctionDef):
            args = [a.arg for a in node.args.args]
            firmas_orig.add(f"{node.name}({','.join(args)})")

    for node in ast.walk(tree_final):
        if isinstance(node, ast.FunctionDef):
            args = [a.arg for a in node.args.args]
            firmas_final.add(f"{node.name}({','.join(args)})")

    perdidas = firmas_orig - firmas_final
    if perdidas:
        return False, [f"Firma perdida: {f}" for f in perdidas]

    return True, []


def verificar_mapa_cromatico(
    mapa: dict,
    codigo_original: str,
    codigo_final: str,
) -> tuple[bool, str]:
    """Verifica que el mapa cromático se mantenga tras el refactor.

    🔴 Rojas: deben coincidir en número (mismas instrucciones lógicas)
    🟢 Verdes: los gaps se reconstruyen después, no se verifican aquí

    Returns:
        (ok, mensaje)

    """
    if not mapa or mapa.get("tipo") == "fallback_syntax":
        return True, "Sin mapa cromático (fallback)"

    rojas_esperadas = mapa.get("total_rojas", 0)

    # Contar 🔴 reales en el código final
    try:
        arbol = ast.parse(codigo_final)
    except SyntaxError:
        return False, "No se puede verificar mapa: código final no compila"

    rojas_reales = 0
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if hasattr(nodo, "end_lineno") and nodo.end_lineno:
                rojas_reales += 1
        if isinstance(nodo, (ast.For, ast.While, ast.If, ast.Try, ast.With)):
            for body_node in getattr(nodo, "body", []):
                if hasattr(body_node, "end_lineno") and body_node.end_lineno:
                    rojas_reales += 1

    if rojas_reales < rojas_esperadas * 0.5:
        return False, (
            f"🔴 Colapso cromático: {rojas_reales} rojas vs {rojas_esperadas} esperadas "
            f"(-{int((1-rojas_reales/rojas_esperadas)*100)}%). "
            "El refactor eliminó demasiadas instrucciones lógicas."
        )

    if rojas_reales > rojas_esperadas * 2:
        return False, (
            f"🔴 Explosión cromática: {rojas_reales} rojas vs {rojas_esperadas} esperadas "
            f"(+{int((rojas_reales/rojas_esperadas-1)*100)}%). "
            "El refactor creó demasiadas instrucciones nuevas."
        )

    return True, f"✅ Mapa cromático: {rojas_reales}/{rojas_esperadas} 🔴"


def compactar(
    ruta_original: Path,
    ruta_nuevo_codigo: Path,
    metadata: dict,
    dry_run: bool = False,
    mapa_cromatico: dict | None = None,
) -> dict:
    """Ejecuta el pipeline completo de compactación.

    Args:
        ruta_original: Archivo original.
        ruta_nuevo_codigo: Código refactorizado (solo la función).
        metadata: Metadata del fragmentador.
        dry_run: Si True, no escribe el archivo.

    Returns:
        Dict con resultado del proceso.

    """
    codigo_original = ruta_original.read_text(encoding="utf-8")
    codigo_nuevo = ruta_nuevo_codigo.read_text(encoding="utf-8")

    # 1. Extraer chincheta del ORIGINAL (no del nuevo)
    start_line = metadata["start_line"]
    end_line = metadata["end_line"]
    nombre_func = metadata.get("function_name", "desconocida")

    # 2. Verificar compile del nuevo código
    compile_ok, compile_err = verificar_compile(codigo_nuevo, ruta_nuevo_codigo.name)
    if not compile_ok:
        return {"status": "ERROR", "fase": "compile_nuevo", "error": compile_err}

    # 3. Inyección quirúrgica
    codigo_final = inyeccion_quirurgica(codigo_original, start_line, end_line, codigo_nuevo)

    # 4. Verificar compile del resultado final
    compile_final_ok, compile_final_err = verificar_compile(codigo_final, ruta_original.name)
    if not compile_final_ok:
        return {"status": "ERROR", "fase": "compile_final", "error": compile_final_err}

    # 5. Verificar firmas AST
    firmas_ok, firmas_err = verificar_firma_ast(codigo_original, codigo_final)
    if not firmas_ok:
        return {"status": "ERROR", "fase": "firmas_ast", "errores": firmas_err}

    # 6. Verificar contabilidad de tokens
    contabilidad_ok, reporte = validar_contabilidad(metadata, codigo_original, codigo_final)

    if not contabilidad_ok:
        return {"status": "WARN", "fase": "contabilidad", "reporte": reporte}

    # 7. Verificar mapa cromático 🔴🟢 (si está disponible)
    cromatico_ok, cromatico_msg = verificar_mapa_cromatico(mapa_cromatico, codigo_original, codigo_final)
    if not cromatico_ok:
        return {"status": "ERROR", "fase": "cromatico", "error": cromatico_msg}

    # 7. Escribir (si no es dry-run)
    if not dry_run:
        backup = ruta_original.with_suffix(".py.bak3")
        if not backup.exists():
            shutil.copy2(ruta_original, backup)

        ruta_original.write_text(codigo_final, encoding="utf-8")

        # Ruff fix post-escritura
        subprocess.run(
            ["ruff", "check", "--fix", "--unsafe-fixes", str(ruta_original)],
            capture_output=True, timeout=30,
        )
        subprocess.run(
            ["ruff", "format", str(ruta_original)],
            capture_output=True, timeout=30,
        )

    return {
        "status": "OK",
        "archivo": str(ruta_original),
        "funcion": nombre_func,
        "start_line": start_line,
        "end_line": end_line,
        "lineas_nuevas": len(codigo_nuevo.splitlines()),
        "contabilidad": reporte,
        "cromatico": cromatico_msg,
    }


def scan_project() -> None:
    from pathlib import Path as _Path
    root = _Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Compactadora Determinista")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--metadata", help="JSON con metadata del fragmentador")
    parser.add_argument("--nuevo-codigo", help="Archivo con código refactorizado")
    parser.add_argument("--original", help="Archivo original")
    parser.add_argument("--mapa-cromatico", help="JSON con mapa cromático 🔴🟢")
    parser.add_argument("--dry-run", action="store_true", help="Solo validar, no escribir")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    meta = parse_metadata(Path(args.metadata))
    mapa = None
    if args.mapa_cromatico:
        mapa = parse_metadata(Path(args.mapa_cromatico))

    resultado = compactar(
        Path(args.original),
        Path(args.nuevo_codigo),
        meta,
        dry_run=args.dry_run,
        mapa_cromatico=mapa,
    )

    if resultado["status"] == "ERROR":
        sys.exit(1)


if __name__ == "__main__":
    main()
