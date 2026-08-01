"""Inventario reproducible de funciones de produccion (LOC y complejidad ciclomatica).

Sprint F5 — regenera data/baseline/radon.txt y data/baseline/loc_heavy.txt (M3).

Uso:
    python3 scripts/pro/inventario_f5.py                # tabla markdown + totales
    python3 scripts/pro/inventario_f5.py --json out.json
    python3 scripts/pro/inventario_f5.py --write        # regenera baselines en data/baseline/

Formula ciclomatica: identica a scripts/pro/arq_auditor.py::_cclomatic
(edges - nodes + 2, contando If/While/For/ExceptHandler/BoolOp por funcion).
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

URA_ROOT = Path(__file__).resolve().parents[2]

PROD_DIRS = ("core", "motor", "knowledge", "monitor", "mantenimiento", "agents", "config")
EXCLUDE_PARTS = ("test", "tests", "__pycache__", ".venv", "build", ".attic", ".nervioso", "docs", "data", "scripts", "node_modules")


def _is_production(path: Path) -> bool:
    rel = path.relative_to(URA_ROOT)
    return not any(part in EXCLUDE_PARTS for part in rel.parts)


def _function_cc(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    edges = 1
    for n in ast.walk(func):
        if isinstance(n, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With, ast.Assert)):
            edges += 1
        elif isinstance(n, ast.BoolOp):
            edges += len(n.values) - 1
    return edges - 1 + 2


def _walk_functions(tree: ast.AST) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, int]]:
    """Devuelve (nodo, linea_inicio) para funciones, anidadas incluidas."""
    found: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, int]] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append((child, child.lineno))
            visit(child)

    visit(tree)
    return found


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for base in PROD_DIRS:
        base_dir = URA_ROOT / base
        if base_dir.is_dir():
            files.extend(p for p in base_dir.rglob("*.py") if _is_production(p))
    files.extend(p for p in URA_ROOT.glob("*.py"))
    return sorted(set(files))


def analyze() -> dict:
    records: list[dict] = []
    archivos: list[dict] = []
    for file in _iter_files():
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = file.relative_to(URA_ROOT)
        line_count = file.read_text(encoding="utf-8").count("\n")
        archivos.append({"file": str(rel), "loc": line_count})
        for func, _ in _walk_functions(tree):
            loc = func.end_lineno - func.lineno + 1
            cc = _function_cc(func)
            records.append(
                {
                    "file": str(rel),
                    "line": func.lineno,
                    "name": func.name,
                    "loc": loc,
                    "cc": cc,
                }
            )
    longas = sorted((r for r in records if r["loc"] > 60), key=lambda r: (-r["cc"], -r["loc"]))
    complejas = sorted((r for r in records if r["cc"] >= 20), key=lambda r: (-r["cc"], -r["loc"]))
    return {
        "funciones_totales": len(records),
        "funciones_gt_60": len(longas),
        "funciones_cc_ge_20": len(complejas),
        "longas": longas,
        "complejas": complejas,
        "archivos": sorted(archivos, key=lambda a: -a["loc"]),
    }


def render_table(rows: list[dict]) -> str:
    lines = ["| Archivo | Linea | Funcion | LOC | CC |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['file']} | {r['line']} | {r['name']} | {r['loc']} | {r['cc']} |")
    return "\n".join(lines)


def write_baselines(result: dict) -> None:
    baseline_dir = URA_ROOT / "data" / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    radon = baseline_dir / "radon.txt"
    radon_lines = [f"funciones con complejidad >= 20: {result['funciones_cc_ge_20']}\n"]
    for r in sorted(result["complejas"], key=lambda r: (-r["cc"], -r["loc"])):
        radon_lines.append(f"  {r['file']}:{r['line']} {r['name']} CC={r['cc']}\n")
    radon.write_text("".join(radon_lines))
    heavy = baseline_dir / "loc_heavy.txt"
    total = sum(a["loc"] for a in result["archivos"])
    heavy_lines = [f"  {total} total\n"]
    for a in result["archivos"]:
        heavy_lines.append(f"  {a['loc']} {a['file']}\n")
    heavy.write_text("".join(heavy_lines))
    print(f"Baselines regenerados: {radon.name} ({result['funciones_cc_ge_20']} cc>=20), {heavy.name} ({total} LOC)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", metavar="OUT", help="escribir inventario completo en JSON")
    parser.add_argument("--write", action="store_true", help="regenerar data/baseline/radon.txt y loc_heavy.txt")
    args = parser.parse_args()

    result = analyze()
    print(f"Archivos analizados: {len(result['archivos'])}")
    print(f"Funciones totales: {result['funciones_totales']}")
    print(f"Funciones >60 lineas: {result['funciones_gt_60']}")
    print(f"Funciones CC >= 20: {result['funciones_cc_ge_20']}")
    print("\n=== CC >= 20 ===")
    print(render_table(result["complejas"]))
    print("\n=== LOC > 60 (top 25) ===")
    print(render_table(result["longas"][:25]))

    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\nJSON escrito en {args.json}")
    if args.write:
        write_baselines(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
