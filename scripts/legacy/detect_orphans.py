#!/usr/bin/env python3
"""Detección estricta de archivos huérfanos en core/ y agents/."""

import os
import ast
import json
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent.parent
TARGETS = [BASE / "core", BASE / "agents"]
EXCLUDE = {"__pycache__", ".venv", ".git", "logs", "backup"}


def find_py_files(directory):
    files = []
    for root, dirs, filenames in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
        for f in filenames:
            if f.endswith(".py"):
                files.append(Path(root) / f)
    return files


def extract_imports(filepath):
    imports = set()
    try:
        tree = ast.parse(filepath.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    except SyntaxError:
        return {"<SYNTAX_ERROR>"}
    except Exception:
        return {"<PARSE_ERROR>"}
    return imports


# Find all files
all_files = []
for target in TARGETS:
    all_files.extend(find_py_files(target))

print(f"📊 Total archivos: {len(all_files)}")
print()

# Map: filename (stem) → full path
stem_to_paths = defaultdict(list)
for f in all_files:
    stem_to_paths[f.stem].append(f)

# Build import graph
file_imports = {}
for f in all_files:
    file_imports[str(f)] = extract_imports(f)

# What stems are imported by anyone?
imported_stems = set()
for f, imports in file_imports.items():
    for imp in imports:
        imported_stems.add(imp)

# Find orphans: files whose stem is NEVER imported AND doesn't import from siblings
orphans = []
for f in all_files:
    stem = f.stem
    rel = str(f.relative_to(BASE))

    # A file is orphan if:
    # 1. Its stem name is not imported by ANY other file
    # 2. AND it doesn't have a __main__ block (can be run standalone)
    # 3. AND it doesn't import from any sibling in the same dir
    is_imported = stem in imported_stems

    has_main = False
    try:
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and hasattr(node.test, "left"):
                try:
                    if (
                        hasattr(node.test.left, "id")
                        and node.test.left.id == "__name__"
                        and hasattr(node.test.comparators[0], "value")
                        and node.test.comparators[0].value == "__main__"
                    ):
                        has_main = True
                except:
                    pass
    except:
        pass

    # Check if it imports from its own directory or sibling dirs
    own_imports = file_imports.get(str(f), set())
    imports_siblings = any(i in stem_to_paths for i in own_imports)

    if not is_imported and not has_main and not imports_siblings:
        orphans.append((rel, "sin imports + sin referencias"))
    elif not is_imported and not has_main and imports_siblings:
        orphans.append(
            (
                rel,
                f"importa a otros ({', '.join(sorted(own_imports & set(stem_to_paths.keys()))[:3] or ['?'])}), pero nadie lo importa",
            )
        )

# Results
print("🔍 ANÁLISIS DE HUÉRFANOS")
print(f"{'=' * 70}")

definitely_orphan = [(f, r) for f, r in orphans if "sin imports" in r]
maybe_orphan = [(f, r) for f, r in orphans if "importa a otros" in r]

print(f"\n❌ DEFINITIVAMENTE HUÉRFANOS ({len(definitely_orphan)}):")
print("   (sin imports, sin __main__, sin referencias cruzadas)")
for f, reason in sorted(definitely_orphan):
    size = (BASE / f).stat().st_size
    print(f"   {f} ({size // 1024}KB)")

print(f"\n⚠️  PROBABLEMENTE HUÉRFANOS ({len(maybe_orphan)}):")
print("   (importan a otros, pero nadie los importa)")
for f, reason in sorted(maybe_orphan):
    size = (BASE / f).stat().st_size
    print(f"   {f} ({size // 1024}KB)")

# Stats
imported_count = sum(1 for f in all_files if f.stem in imported_stems)
print("\n📈 ESTADÍSTICAS:")
print(f"   Total archivos: {len(all_files)}")
print(f"   Importados por otros: {imported_count}")
print(f"   Huérfanos totales: {len(orphans)}")
print(f"   Definitivos: {len(definitely_orphan)}")
print(f"   Probables: {len(maybe_orphan)}")

# Save report
report = {
    "total_files": len(all_files),
    "imported": imported_count,
    "orphans_definite": [f for f, _ in definitely_orphan],
    "orphans_probable": [f for f, _ in maybe_orphan],
    "generated_by": "scripts/detect_orphans.py",
}
report_path = BASE / "docs" / "orphan_report.json"
report_path.parent.mkdir(exist_ok=True)
with open(report_path, "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print(f"\n📁 Reporte guardado: {report_path}")
