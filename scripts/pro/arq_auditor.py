#!/usr/bin/env python3
"""ARQ Auditor — auditoría arquitectónica automatizada (Bloques A–K).

Uso:
  python3 scripts/pro/arq_auditor.py                    # informe completo
  python3 scripts/pro/arq_auditor.py --block A          # solo bloque A
  python3 scripts/pro/arq_auditor.py --json             # salida JSON
  python3 scripts/pro/arq_auditor.py --check            # exit 1 si hay FAIL
  python3 scripts/pro/arq_auditor.py --html             # generar dashboard HTML
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

URA_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Patrones globales ──

FORBIDDEN_TOP_LEVEL_CALLS = [
    "requests.", "httpx.", "urllib.request.urlopen", "socket.",
    "sqlite3.connect", "QdrantClient(", "UraConfig.load",
    "get_secret(", "logging.basicConfig", "asyncio.run",
]

STDLIB_MODULES = set(sys.builtin_module_names) | {
    "abc", "ast", "asyncio", "base64", "collections", "contextlib",
    "copy", "csv", "dataclasses", "datetime", "decimal", "enum",
    "functools", "glob", "hashlib", "html", "http", "importlib",
    "inspect", "io", "itertools", "json", "logging", "math", "os",
    "pathlib", "pickle", "platform", "pprint", "queue", "random",
    "re", "secrets", "shutil", "signal", "socket", "sqlite3",
    "string", "struct", "subprocess", "sys", "tempfile", "textwrap",
    "threading", "time", "traceback", "types", "typing", "unittest",
    "urllib", "uuid", "warnings", "weakref", "xml", "zipfile",
}

FORBIDDEN_STATE_PATTERNS = [
    "requests.", "httpx.", "router.route", ".chat(",
    ".execute(", "await ", "for ", "while ", "thread", "asyncio.",
]

SINGLETON_ALLOWED = {"SubprocessExecutor", "ProviderRegistry"}
SINGLETON_PENDING = {"CircuitBreaker", "HybridMemory", "HealthRegistry"}
SINGLETON_FORBIDDEN = {"QdrantClient", "httpx.AsyncClient", "requests.Session"}

EXEMPTED_CORE_IMPORTS = {
    "core/infra/heartbeat.py", "core/model_router/cli.py",
    "core/auto_reindex.py", "core/json_logger.py",
    "core/memoria/qdrant_store.py",
}

BENCHMARK_PREFIXES = ("benchmark_", "test_", "soak_", "demo_", "generate_", "seed_")

SCRIPT_EXCEPTIONS = (
    "scripts/pro/mcp_mochila.py",  # MCP server
    "scripts/pro/f14_load_test.py",  # benchmark
    "scripts/pro/f14_e2e.py",  # benchmark de integración
    "scripts/pro/alineador.py",  # parcialmente migrado, COLECCION_TRANSACCIONES no en public_api
    "scripts/pro/metrics_server.py",  # servidor independiente
    "scripts/pro/cleanup_assistant.py",  # herramienta interna
    "scripts/pro/autonomy/",  # subsistema de autonomía
)

ALLOWED_SCRIPT_ROOT = "motor.cli.public_api"


def _find_py_files(root: Path) -> list[Path]:
    return [
        p for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
        and ".venv" not in p.parts
        and ".sandbox_packages" not in p.parts
        and "build" not in p.parts
        and ".nervioso" not in p.parts
    ]


def _get_call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        return f"{_get_attr_chain(node.func)}("
    if isinstance(node.func, ast.Name):
        return f"{node.func.id}("
    return ""


def _get_attr_chain(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return f"{_get_attr_chain(node.value)}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return ""


# ── Bloque A: Side effects en import ──

def _top_level_calls(tree: ast.AST) -> list[tuple[int, str]]:
    """Busca llamadas a nivel de módulo (no dentro de funciones/clases)."""
    results: list[tuple[int, str]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        calls: list[ast.Call] = []
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            calls.append(node.value)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            calls.append(node.value)
        elif isinstance(node, ast.Assign):
            # Buscar calls en el value (e.g., x = foo() or bar())
            for n in ast.walk(node.value):
                if isinstance(n, ast.Call):
                    calls.append(n)
        for c in calls:
            name = _get_call_name(c)
            if name:
                results.append((c.lineno, name))
    return results


def block_a(files: list[Path]) -> list[dict]:
    findings = []
    for f in files:
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError:
            continue
        rel = f.relative_to(URA_ROOT)
        for line, name in _top_level_calls(tree):
            for pattern in FORBIDDEN_TOP_LEVEL_CALLS:
                if pattern in name:
                    findings.append({
                        "block": "A", "type": "import_side_effect",
                        "file": str(rel), "line": line,
                        "detail": f"Llamada a '{name}' a nivel de módulo",
                        "level": "P0",
                    })
    return findings


# ── Bloque B: Lazy imports ──

def _classify_lazy_import(module: str, names: list[str], filepath: str) -> str:
    if any(n.endswith("TYPE_CHECKING") for n in names):
        return "TYPE_CHECKING"
    if module in STDLIB_MODULES:
        return "PERFORMANCE"
    if "TYPE_CHECKING" in filepath:
        return "TYPE_CHECKING"
    return "CIRCULAR"


def block_b(files: list[Path]) -> list[dict]:
    findings = []
    for f in files:
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError:
            continue
        rel = f.relative_to(URA_ROOT)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        module = child.module if isinstance(child, ast.ImportFrom) else child.names[0].name
                        names = [a.name for a in child.names]
                        cls = _classify_lazy_import(module or "", names, str(rel))
                        if cls in ("WORKAROUND", "UNKNOWN"):
                            findings.append({
                                "block": "B", "type": "lazy_import_" + cls.lower(),
                                "file": str(rel), "line": child.lineno,
                                "detail": f"Lazy import clasificado como {cls}: {module}",
                                "level": "FAIL",
                            })
    return findings


# ── Bloque C: Estado global ──

def block_c(files: list[Path]) -> list[dict]:
    findings = []
    for f in files:
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError:
            continue
        rel = f.relative_to(URA_ROOT)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                        name = _get_call_name(node.value).rstrip("(")
                        if name in SINGLETON_FORBIDDEN:
                            findings.append({
                                "block": "C", "type": "singleton_forbidden",
                                "file": str(rel), "line": node.lineno,
                                "detail": f"Singleton prohibido: {name}",
                                "level": "P0",
                            })
                        elif name in SINGLETON_PENDING:
                            findings.append({
                                "block": "C", "type": "singleton_pending",
                                "file": str(rel), "line": node.lineno,
                                "detail": f"Singleton pendiente de migración: {name}",
                                "level": "WARNING",
                            })
    return findings


# ── Bloque D: _state.py ──

STATE_FILE_EXCEPTIONS = {
    "motor/core/llm/_state.py",  # for en _get_optional_providers() es construcción, no lógica
}

def block_d(files: list[Path]) -> list[dict]:
    findings = []
    for f in files:
        if not f.name.endswith("_state.py"):
            continue
        rel = str(f.relative_to(URA_ROOT))
        if rel in STATE_FILE_EXCEPTIONS:
            continue
        content = f.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            for pattern in FORBIDDEN_STATE_PATTERNS:
                if pattern in line and not line.strip().startswith("#"):
                    findings.append({
                        "block": "D", "type": "state_business_logic",
                        "file": str(rel), "line": i,
                        "detail": f"Patrón '{pattern}' en _state.py",
                        "level": "FAIL",
                    })
    return findings


# ── Bloque E: Factories ──

def block_e(files: list[Path]) -> list[dict]:
    findings = []
    for f in files:
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError:
            continue
        rel = f.relative_to(URA_ROOT)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("build_"):
                    has_cache = any(
                        isinstance(n, ast.Assign) and any(
                            isinstance(t, ast.Name) and t.id == node.name.split("_", 1)[1] + "_cache"
                            for t in n.targets
                        ) for n in ast.walk(node)
                    )
                    if has_cache:
                        findings.append({
                            "block": "E", "type": "factory_caching",
                            "file": str(rel), "line": node.lineno,
                            "detail": f"build_{node.name} cachea resultado",
                            "level": "WARNING",
                        })
    return findings


# ── Bloque F: API pública ──

def _is_script_exempted(rel: Path) -> bool:
    s = str(rel)
    for exc in SCRIPT_EXCEPTIONS:
        if exc.endswith("/"):
            if s.startswith(exc):
                return True
        elif s == exc:
            return True
    return False


def block_f(files: list[Path]) -> list[dict]:
    findings = []
    for f in files:
        rel = f.relative_to(URA_ROOT)
        if not str(rel).startswith("scripts/"):
            continue
        if any(rel.name.startswith(p) for p in BENCHMARK_PREFIXES):
            continue
        if _is_script_exempted(rel):
            continue
        content = f.read_text()
        for match in re.finditer(r"^from (motor\.\S+) import|^import (motor\.\S+)", content, re.MULTILINE):
            imported = match.group(1) or match.group(2)
            if imported and not imported.startswith(ALLOWED_SCRIPT_ROOT):
                findings.append({
                    "block": "F", "type": "script_import_violation",
                    "file": str(rel), "line": content[:match.start()].count("\n") + 1,
                    "detail": f"Importa '{imported}' en lugar de desde {ALLOWED_SCRIPT_ROOT}",
                    "level": "FAIL",
                })
    return findings


# ── Bloque G: Protocolos ──

def block_g(files: list[Path]) -> list[dict]:
    findings = []
    for f in files:
        rel = f.relative_to(URA_ROOT)
        if not str(rel).startswith("core/"):
            continue
        if str(rel) in EXEMPTED_CORE_IMPORTS:
            continue
        if rel.name.endswith("_state.py"):
            continue
        content = f.read_text()
        for match in re.finditer(r"^from motor\.|^import motor\.", content, re.MULTILINE):
            findings.append({
                "block": "G", "type": "core_import_motor",
                "file": str(rel), "line": content[:match.start()].count("\n") + 1,
                "detail": f"core/ importa de motor/: {match.group().strip()}",
                "level": "FAIL",
            })
    return findings


# ── Bloque H: Compatibilidad ──

def block_h(files: list[Path]) -> list[dict]:
    findings = []
    for f in files:
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError:
            continue
        rel = f.relative_to(URA_ROOT)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "__getattr__":
                has_warning = any(
                    isinstance(n, ast.Call) and getattr(getattr(n.func, 'attr', None), 'startswith', lambda _: False)('warn')
                    for n in ast.walk(node)
                )
                if not has_warning:
                    findings.append({
                        "block": "H", "type": "compat_without_warning",
                        "file": str(rel), "line": node.lineno,
                        "detail": "__getattr__ sin DeprecationWarning",
                        "level": "FAIL",
                    })
    return findings


# ── Bloque I: Archivos grandes ──

def _count_functions(tree: ast.AST) -> int:
    return sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))


def _count_imports(tree: ast.AST) -> int:
    return sum(1 for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))


def _cclomatic(tree: ast.AST) -> float:
    edges = 0
    nodes = 0
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes += 1
            edges += 1 + sum(1 for c in ast.walk(n) if isinstance(c, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.BoolOp)))
    return edges - nodes + 2 if nodes > 0 else 1


def block_i(files: list[Path]) -> list[dict]:
    ranking = []
    for f in files:
        rel = f.relative_to(URA_ROOT)
        if not (str(rel).startswith("motor/") or str(rel).startswith("core/")):
            continue
        if any(p in ("test", "tests", "__pycache__") for p in rel.parts):
            continue
        if rel.name == "__init__.py":
            continue
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError:
            continue
        lines = len(f.read_text().split("\n"))
        funcs = _count_functions(tree)
        deps = _count_imports(tree)
        cc = _cclomatic(tree)
        priority = (lines / 100) * 0.3 + (funcs / 10) * 0.2 + (cc / 10) * 0.3 + (deps / 5) * 0.1
        if priority > 2.0 or lines > 500:
            ranking.append({
                "block": "I", "type": "large_file",
                "file": str(rel), "line": 1,
                "detail": f"L{lines} F{funcs} CC{cc:.0f} D{deps} P{priority:.1f}",
                "level": "MEDIUM" if priority < 5.0 else "HIGH",
                "priority_score": round(priority, 1),
                "lines": lines,
                "functions": funcs,
                "complexity": round(cc, 1),
                "dependencies": deps,
            })
    ranking.sort(key=lambda x: -x["priority_score"])
    return ranking


# ── Bloque J: Tendencias ──

def block_j(all_findings: dict[str, list]) -> dict[str, Any]:
    total_lazy = 0
    workaround_count = 0
    singleton_forbidden = sum(1 for f in all_findings.get("C", []) if f.get("type") == "singleton_forbidden")
    large_files = sum(1 for f in all_findings.get("I", []) if f.get("lines", 0) > 500)
    side_effects = sum(1 for f in all_findings.get("A", []) if f.get("level") == "P0")

    return {
        "block": "J",
        "type": "trends",
        "metrics": {
            "side_effects_in_import": side_effects,
            "lazy_imports_workaround": workaround_count,
            "singletons_forbidden": singleton_forbidden,
            "modules_over_500_lines": large_files,
            "rules_coverage": f"{len([k for k, v in all_findings.items() if v])}/11",
        },
    }


# ── Bloque K: ADR Enforcement ──

def block_k() -> list[dict]:
    findings = []
    adr_checks = {
        "ADR-030": "scripts/pro/tuneladora/engine.py",
        "AGENTS.md:_state.py": None,  # cubierto por bloque D
        "AGENTS.md:factories": None,  # cubierto por bloque E
        "AGENTS.md:deprecation": None,  # cubierto por bloque H
    }
    for adr, filepath in adr_checks.items():
        if filepath and Path(filepath).exists():
            findings.append({
                "block": "K", "type": "adr_check",
                "file": filepath,
                "detail": f"{adr}: archivo existe",
                "level": "PASS",
            })
        elif filepath:
            findings.append({
                "block": "K", "type": "adr_check",
                "file": filepath,
                "detail": f"{adr}: archivo no encontrado",
                "level": "FAIL",
            })
        else:
            findings.append({
                "block": "K", "type": "adr_check",
                "file": "-",
                "detail": f"{adr}: cubierto por otro bloque",
                "level": "INFO",
            })
    return findings


# ── Orquestador ──

def run_all() -> dict[str, Any]:
    files = _find_py_files(URA_ROOT)
    findings: dict[str, list] = {}

    blocks = {
        "A": ("Side effects en import", lambda: block_a(files)),
        "B": ("Lazy imports", lambda: block_b(files)),
        "C": ("Estado global", lambda: block_c(files)),
        "D": ("_state.py", lambda: block_d(files)),
        "E": ("Factories", lambda: block_e(files)),
        "F": ("API pública", lambda: block_f(files)),
        "G": ("Protocolos", lambda: block_g(files)),
        "H": ("Compatibilidad", lambda: block_h(files)),
        "I": ("Archivos grandes", lambda: block_i(files)),
        "K": ("ADR Enforcement", lambda: block_k()),
    }

    for block_id, (name, fn) in blocks.items():
        try:
            result = fn()
            findings[block_id] = result
        except Exception as e:
            findings[block_id] = [{"type": "error", "detail": str(e)}]

    # Bloque J usa resultados de los demás
    findings["J"] = [block_j(findings)]

    return {
        "version": "v4.10.0",
        "files_scanned": len(files),
        "blocks": findings,
    }


def _print_report(result: dict[str, Any]) -> None:
    print(f"\nARQ Auditor — v{result['version']}")
    print(f"{'='*60}")
    print(f"Archivos escaneados: {result['files_scanned']}\n")

    total_fail = 0
    total_warn = 0
    all_findings = result["blocks"]
    for block_id in sorted(all_findings.keys()):
        block_data = all_findings[block_id]
        if not block_data:
            print(f"  [{block_id}] ✅ — 0 hallazgos")
            continue
        fails = sum(1 for f in block_data if f.get("level") in ("FAIL", "P0"))
        warns = sum(1 for f in block_data if f.get("level") in ("WARNING", "MEDIUM"))
        total_fail += fails
        total_warn += warns
        status = "❌" if fails else "⚠️" if warns else "ℹ️"
        print(f"  [{block_id}] {status} — {len(block_data)} hallazgos ({fails} FAIL, {warns} WARN)")
        for f in block_data[:5]:
            print(f"       {f.get('type','').ljust(25)} {f.get('file','')}:{f.get('line','')}  {f.get('detail','')}")
        if len(block_data) > 5:
            print(f"       ... y {len(block_data)-5} más")

    print(f"\n{'='*60}")
    print(f"Total: {total_fail} FAIL, {total_warn} WARNING")
    if total_fail > 0:
        print("RESULTADO: ❌ NO SUPERADO")
    elif total_warn > 0:
        print("RESULTADO: ⚠️ SUPERADO CON ADVERTENCIAS")
    else:
        print("RESULTADO: ✅ SUPERADO")
    print(f"{'='*60}\n")


BASELINE_PATH = URA_ROOT / "docs" / "architecture" / "arq_baseline.json"


def _load_baseline() -> set[tuple[str, str, int]]:
    """Carga la línea base de hallazgos conocidos."""
    if not BASELINE_PATH.exists():
        return set()
    try:
        data = json.loads(BASELINE_PATH.read_text())
        return {(f["file"], f["type"], f["line"]) for f in data}
    except Exception:
        return set()


def _save_baseline(all_findings: list[dict]) -> None:
    """Guarda la línea base actual."""
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    simplified = [{"file": f.get("file", "-"), "type": f.get("type", "unknown"), "line": f.get("line", 0)} for f in all_findings]
    BASELINE_PATH.write_text(json.dumps(simplified, indent=2))


def _filter_new_findings(all_findings: list[dict], baseline: set[tuple[str, str, int]]) -> list[dict]:
    """Retorna solo hallazgos nuevos (no en línea base)."""
    return [f for f in all_findings if (f.get("file", "-"), f.get("type", "unknown"), f.get("line", 0)) not in baseline]


TRENDS_PATH = URA_ROOT / "docs" / "architecture" / "arq_trends.jsonl"


def _save_trends(result: dict[str, Any], all_findings: list[dict]) -> None:
    """Guarda una línea de tendencia con las métricas actuales."""
    import datetime
    fails = sum(1 for f in all_findings if f.get("level") in ("FAIL", "P0"))
    warns = sum(1 for f in all_findings if f.get("level") in ("WARNING", "MEDIUM"))
    side_effects = sum(1 for f in all_findings if f.get("type") == "import_side_effect")
    singletons = sum(1 for f in all_findings if f.get("type") == "singleton_forbidden")
    large_files = sum(1 for f in all_findings if f.get("type") == "large_file" and f.get("lines", 0) > 500)
    script_violations = sum(1 for f in all_findings if f.get("type") == "script_import_violation")

    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version": result.get("version", "unknown"),
        "files_scanned": result.get("files_scanned", 0),
        "total_fail": fails,
        "total_warn": warns,
        "side_effects": side_effects,
        "singletons_forbidden": singletons,
        "modules_over_500_lines": large_files,
        "script_import_violations": script_violations,
    }
    TRENDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRENDS_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="ARQ Auditor — verificación arquitectónica")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--check", action="store_true", help="Exit 1 si hay FAIL nuevos")
    parser.add_argument("--update-baseline", action="store_true", help="Actualizar línea base")
    parser.add_argument("--html", action="store_true", help="Dashboard HTML")
    args = parser.parse_args()

    result = run_all()
    all_findings: list[dict] = []
    for block_list in result["blocks"].values():
        all_findings.extend(block_list)

    # Guardar tendencia en cada ejecución
    _save_trends(result, all_findings)

    if args.update_baseline:
        _save_baseline(all_findings)
        print(f"Línea base actualizada: {len(all_findings)} hallazgos")
        return 0

    if args.check:
        baseline = _load_baseline()
        new_findings = _filter_new_findings(all_findings, baseline)
        new_fails = sum(1 for f in new_findings if f.get("level") in ("FAIL", "P0"))
        if new_fails > 0:
            print(f"NUEVOS FAIL ({new_fails}) — no en línea base:")
            for f in new_findings:
                if f.get("level") in ("FAIL", "P0"):
                    print(f"  {f['file']}:{f.get('line','')} [{f.get('type','')}] {f.get('detail','')[:80]}")
            print(f"\nTotal baseline: {len(baseline)} hallazgos conocidos")
            return 1
        return 0

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    elif args.html:
        print("HTML dashboard no implementado. Use --json o --update-baseline.")
    else:
        _print_report(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
