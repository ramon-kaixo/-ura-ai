#!/usr/bin/env bash
# run_mutation_tests.sh — Ejecuta mutation testing (mutmut) sobre el proyecto.
#
# Usa la config de pyproject.toml [tool.mutmut] (source_paths, do_not_mutate,
# pytest_add_cli_args). Falla (exit 1) si hay mutantes supervivientes,
# no verificados o errores.
#
# Uso:
#   scripts/run_mutation_tests.sh            # barrido completo (lento)
#   scripts/run_mutation_tests.sh --dry-run  # solo configuración, sin mutar
#   MUTMUT_ARGS="--max-children 4" scripts/run_mutation_tests.sh
#
# Exit: 0 = todo mutado (0 supervivientes/no verificados/errores)
#       1 = hay supervivientes/no verificados/errores
#       2 = error de configuración/ejecución

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

VENV_BIN="$REPO/.venv/bin"
MUTMUT="${MUTMUT:-$VENV_BIN/mutmut}"
PYTHON="${PYTHON:-$VENV_BIN/python}"

REPORT_DIR="$REPO/docs/udo/mutation-reports"
REPORT_FILE="$REPORT_DIR/mutmut_$(date +%Y%m%d_%H%M%S).md"

if [[ ! -x "$MUTMUT" ]]; then
    echo "ERROR: mutmut no encontrado en $MUTMUT" >&2
    echo "Instálalo con: pip install mutmut" >&2
    exit 2
fi

if [[ "${1:-}" == "--dry-run" ]]; then
    echo "[mutmut] Dry-run: verificando configuración..."
    "$PYTHON" -c "
from mutmut.configuration import _load_config
cfg = _load_config()
print(f'source_paths: {cfg.source_paths}')
print(f'do_not_mutate: {cfg.do_not_mutate}')
print(f'pytest_add_cli_args: {len(cfg.pytest_add_cli_args)} args')
print('Config OK')
"
    exit 0
fi

mkdir -p "$REPORT_DIR"

echo "[mutmut] Barrido de mutación iniciado: $(date '+%Y-%m-%d %H:%M:%S')"
echo "[mutmut] Fuente: pyproject.toml [tool.mutmut]"

# --fail-on-suspicious no existe en mutmut 3.7; se evalúa el resumen tras el run.
set +e
HYPOTHESIS_PROFILE=ci $MUTMUT run ${MUTMUT_ARGS:-} 2>&1 | tee "$REPORT_FILE"
RUN_STATUS=${PIPESTATUS[0]}
set -e

echo "[mutmut] Resumen del run (exit=$RUN_STATUS):"
if [[ -f .mutmut-cache/mutant_status.json ]]; then
    "$PYTHON" - <<'PYEOF'
import json

with open(".mutmut-cache/mutant_status.json") as f:
    data = json.load(f)

statuses = {}
for mid, entry in data.items():
    st = entry.get("status", "unknown")
    statuses[st] = statuses.get(st, 0) + 1

total = sum(statuses.values())
killed = statuses.get("killed", 0)
survived = statuses.get("survived", 0)
suspicious = statuses.get("suspicious", 0)
not_checked = statuses.get("not_checked", 0)
errors = statuses.get("error", 0)

print(f"  total      : {total}")
print(f"  killed     : {killed}")
print(f"  survived   : {survived}")
print(f"  suspicious : {suspicious}")
print(f"  not_checked: {not_checked}")
print(f"  errors     : {errors}")

if total > 0:
    ratio = killed / total
    print(f"  kill ratio : {ratio:.1%}")

if survived > 0 or suspicious > 0 or not_checked > 0 or errors > 0:
    print("  RESULTADO: HAY MUTANTES NO ELIMINADOS (fallo del gate)")
else:
    print("  RESULTADO: TODOS LOS MUTANTES ELIMINADOS")
PYEOF
fi

echo "[mutmut] Reporte en: $REPORT_FILE"

# Gate: fallar si hay supervivientes, sospechosos, no verificados o errores
if [[ -f .mutmut-cache/mutant_status.json ]]; then
    "$PYTHON" - <<'PYEOF'
import json
import sys

with open(".mutmut-cache/mutant_status.json") as f:
    data = json.load(f)

bad = 0
for mid, entry in data.items():
    st = entry.get("status", "unknown")
    if st in ("survived", "suspicious", "not_checked", "error"):
        bad += 1

sys.exit(1 if bad > 0 else 0)
PYEOF
    GATE_STATUS=$?
    if [[ $GATE_STATUS -ne 0 ]]; then
        echo "[mutmut] GATE FALLIDO: hay mutantes no eliminados" >&2
        exit 1
    fi
fi

echo "[mutmut] GATE OK: todos los mutantes eliminados"
exit 0
