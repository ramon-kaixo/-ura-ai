#!/usr/bin/env python3
"""ARQ-600: Validación funcional automatizada.

Detecta:
  1. Módulos sin consumidores (definen API pero nadie los importa)
  2. Plugins nunca invocados (registrados pero sin llamadas)
  3. Migraciones incompletas (módulos deprecados con consumidores activos)
  4. Código huérfano (archivos en motor/core sin imports externos)

Uso:
  python3 scripts/pro/arq_checker.py                    # stdout
  python3 scripts/pro/arq_checker.py --json             # JSON output
  python3 scripts/pro/arq_checker.py --check            # exit 1 si hay hallazgos
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

URA_ROOT = Path(__file__).resolve().parent.parent.parent

DEPRECATED_MODULES: dict[str, str] = {
    "core/json_logger.py": "Usar motor.platform.logging.ComponentLogger (deprecado v3.7.6)",
    "knowledge/engine/logging_config.py": "Usar motor.observability.logging (deprecado v3.7.6)",
}

CORE_MODULES: list[str] = []


IGNORED_PLUGIN_PREFIXES = ("_", "Test", "Mock")


def _find_py_files(root: Path) -> list[Path]:
    return [
        p for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
        and ".venv" not in p.parts
        and ".sandbox_packages" not in p.parts
        and "build" not in p.parts
        and ".nervioso" not in p.parts
    ]


def _extract_imports(filepath: Path) -> set[str]:
    """Extrae imports de un archivo .py (rutas completas)."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def _find_plugin_classes(filepath: Path) -> list[str]:
    """Encuentra clases que heredan de PluginBase."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []
    plugins: list[str] = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for base in node.bases
        if (isinstance(base, ast.Name) and base.id == "PluginBase") or (isinstance(base, ast.Attribute) and base.attr == "PluginBase")
    ]
    return plugins


def check_orphans(files: list[Path]) -> list[dict[str, Any]]:
    """Módulos en motor/core que no son importados por nadie (ruta completa)."""
    all_imports: set[str] = set()
    for f in files:
        all_imports.update(_extract_imports(f))

    orphans: list[dict[str, Any]] = []
    for f in files:
        rel = f.relative_to(URA_ROOT)
        parts = rel.parts
        if parts[0] not in ("motor", "core"):
            continue
        if f.name in ("__init__.py", "__main__.py"):
            continue
        if "test" in parts or "tests" in parts:
            continue
        if ".nervioso" in parts:
            continue
        # Saltar scripts standalone (tienen if __name__ == "__main__")
        content = f.read_text()
        if "if __name__ == \"__main__\":" in content or "if __name__ == '__main__':" in content:
            continue
        # Ruta de importación completa
        full_module = str(rel.with_suffix("")).replace("/", ".")
        module_name = f.stem
        # Verificar si alguien importa por ruta completa o por nombre corto
        imported = full_module in all_imports or module_name in all_imports
        if not imported and ("class " in content or "def " in content):
            orphans.append({
                    "type": "orphan",
                    "file": str(rel),
                    "detail": f"No importado por ningún otro módulo (ruta: {full_module})",
                })
    return orphans


def check_deprecated_in_use(files: list[Path]) -> list[dict[str, Any]]:
    """Módulos deprecados que aún tienen consumidores."""
    all_imports: set[str] = set()
    for f in files:
        all_imports.update(_extract_imports(f))

    findings: list[dict[str, Any]] = []
    for dep_path, reason in DEPRECATED_MODULES.items():
        dep_module = dep_path.replace("/", ".").replace(".py", "")
        dep_name = Path(dep_path).stem
        if dep_name in all_imports or dep_module in all_imports:
            findings.append({
                "type": "deprecated_in_use",
                "file": dep_path,
                "detail": reason,
            })
    return findings


def check_plugin_usage(files: list[Path]) -> list[dict[str, Any]]:
    """Plugins definidos pero nunca invocados vía .execute() o .run()."""
    findings: list[dict[str, Any]] = []
    code_index: dict[str, str] = {}
    for f in files:
        if "/test" in str(f) or "/tests" in str(f):
            continue
        code_index[str(f)] = f.read_text()

    for f in files:
        for plugin_name in _find_plugin_classes(f):
            # Saltar plugins de test (prefijo _ , Test, Mock)
            if any(plugin_name.startswith(p) for p in IGNORED_PLUGIN_PREFIXES):
                continue
            rel = f.relative_to(URA_ROOT)
            call_count = 0
            for path_str, code in code_index.items():
                if Path(path_str) == f:
                    continue
                call_count += code.count(f".{plugin_name}(")
                call_count += code.count(f"{plugin_name}(")
            if call_count == 0:
                findings.append({
                    "type": "plugin_unused",
                    "file": str(rel),
                    "detail": f"Plugin '{plugin_name}' definido pero nunca invocado",
                })
    return findings


def check_migration_completeness(files: list[Path]) -> list[dict[str, Any]]:
    """Verifica que módulos migrados no sigan siendo importados por código activo."""
    findings: list[dict[str, Any]] = []
    all_imports: set[str] = set()
    for f in files:
        all_imports.update(_extract_imports(f))

    for mod in CORE_MODULES:
        mod_name = Path(mod).stem
        full_path = mod.replace("/", ".").replace(".py", "")
        if mod_name in all_imports or full_path in all_imports:
            findings.append({
                "type": "migration_incomplete",
                "file": mod,
                "detail": f"Módulo '{mod_name}' aún tiene consumidores activos",
            })
    return findings


def run_all(ura_root: Path = URA_ROOT) -> dict[str, Any]:
    files = _find_py_files(ura_root)
    findings: list[dict[str, Any]] = []
    findings.extend(check_orphans(files))
    findings.extend(check_deprecated_in_use(files))
    findings.extend(check_plugin_usage(files))
    findings.extend(check_migration_completeness(files))

    return {
        "files_scanned": len(files),
        "total_findings": len(findings),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ARQ-600: Validación funcional")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--check", action="store_true", help="Exit 1 si hay hallazgos")
    args = parser.parse_args()

    result = run_all()
    total = result["total_findings"]

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\nARQ-600: Validación funcional")
        print(f"{'='*50}")
        print(f"Archivos escaneados: {result['files_scanned']}")
        print(f"Hallazgos: {total}\n")
        for f in result["findings"]:
            icon = {"orphan": "👻", "deprecated_in_use": "⚠️", "plugin_unused": "🔌", "migration_incomplete": "🚧"}
            print(f"  {icon.get(f['type'], '•')} [{f['type']}] {f['file']}")
            print(f"    {f['detail']}")
            print()
        print(f"{'='*50}")

    if args.check and total > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
