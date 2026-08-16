#!/usr/bin/env bash
# salud_planes.sh — Ejecuta gates y guarda resultados reales en coordination.json.
# Uso: bash scripts/pro/salud_planes.sh [--no-panel]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

COORD="docs/udo/coordination.json"
TMP_RUFF="$(mktemp)"
TMP_MYPY="$(mktemp)"
TMP_PYTEST="$(mktemp)"
trap 'rm -f "$TMP_RUFF" "$TMP_MYPY" "$TMP_PYTEST"' EXIT

run_ruff() {
    if command -v ruff >/dev/null 2>&1; then
        ruff check . >"$TMP_RUFF" 2>&1 && echo "OK" || echo "FAIL"
    else
        echo "NO VERIFICADO (ruff no instalado)"
    fi
}

run_mypy() {
    if command -v mypy >/dev/null 2>&1; then
        mypy --no-incremental core motor shared >"$TMP_MYPY" 2>&1 && echo "OK" || echo "FAIL"
    else
        echo "NO VERIFICADO (mypy no instalado)"
    fi
}

run_pytest() {
    if command -v pytest >/dev/null 2>&1; then
        pytest -q --tb=short >"$TMP_PYTEST" 2>&1 && echo "OK" || echo "FAIL"
    else
        echo "NO VERIFICADO (pytest no instalado)"
    fi
}

RUFF_RESULT="$(run_ruff)"
MYPY_RESULT="$(run_mypy)"
PYTEST_RESULT="$(run_pytest)"

# Actualizar coordination.json con resultados de gates.
python3 - "$COORD" "$RUFF_RESULT" "$MYPY_RESULT" "$PYTEST_RESULT" <<'PY'
import json
import sys
from pathlib import Path

coord_path = Path(sys.argv[1])
ruff = sys.argv[2]
mypy = sys.argv[3]
pytest = sys.argv[4]

with open(coord_path, encoding="utf-8") as f:
    datos = json.load(f)

for tid in datos.get("tareas", {}):
    tarea = datos["tareas"][tid]
    tarea.setdefault("gates", {})
    tarea["gates"]["ruff"] = ruff
    tarea["gates"]["mypy"] = mypy
    tarea["gates"]["pytest"] = pytest

with open(coord_path, "w", encoding="utf-8") as f:
    json.dump(datos, f, indent=2, ensure_ascii=False)
    f.write("\n")
PY

echo " Gates actualizados en $COORD:"
echo "  ruff:   $RUFF_RESULT"
echo "  mypy:   $MYPY_RESULT"
echo "  pytest: $PYTEST_RESULT"

if [[ "${1:-}" != "--no-panel" ]]; then
    python3 scripts/pro/panel.py
fi
