#!/bin/bash
# buzo_calidad.sh — Rodillo de calidad para la Tuneladora
# Ejecuta los 7 rodillos de calidad antes de cualquier despliegue.
# Integrado con Laia para notificar fallos de seguridad.

set -e

URA_BASE="$(cd "$(dirname "$0")/../../../.." && pwd)"
BRIDGE="$URA_BASE/orquestador/laia_bridge.sh"

if [[ -f "$BRIDGE" ]]; then
    source "$BRIDGE"
fi

cd "$URA_BASE"

echo "=== Rodillo 0: preflight ==="
python3 scripts/preflight_check.py || exit 1

echo "=== Rodillo 1: Ruff fix ==="
ruff check --fix . || true

echo "=== Rodillo 2: Autoflake ==="
autoflake --in-place --recursive --remove-all-unused-imports . || true

echo "=== Rodillo 3: Pytest ==="
pytest --maxfail=3 --tb=short -q

echo "=== Rodillo 4: Bandit ==="
bandit -r . -ll -f json -o bandit_report.json 2>/dev/null || true
if [[ -f bandit_report.json ]] && command -v jq &>/dev/null; then
    HIGH_COUNT=$(jq -r '.metrics._totals.HIGH // 0' bandit_report.json 2>/dev/null || echo "0")
    if [[ "$HIGH_COUNT" -gt 0 ]]; then
        echo "⚠️  Bandit detecto $HIGH_COUNT vulnerabilidades HIGH"
        if type laia_command &>/dev/null; then
            laia_command "Seguridad: bandit detecto $HIGH_COUNT vulnerabilidades HIGH. Revisar bandit_report.json."
        fi
        exit 1
    fi
fi

echo "=== Rodillo 5: Debug guard ==="
find . -name "*.py" -not -path "./.venv/*" -exec grep -l "breakpoint()\|pdb.set_trace()" {} \; | while read -r f; do
    sed -i '' '/breakpoint()/d; /pdb.set_trace()/d' "$f"
    echo "  Eliminado debug en $f"
done

echo "=== Rodillo 6: Auto cleanup verify ==="
CLEANUP_LOG=$(ls -t "$URA_BASE/logs"/auto_cleanup_*.log 2>/dev/null | head -1)
if [[ -n "$CLEANUP_LOG" ]]; then
    tail -n 5 "$CLEANUP_LOG"
else
    echo "  Sin log de auto_cleanup (primera ejecucion)"
fi

echo "=== Rodillo 7: Format ==="
ruff format . || true

echo "✅ Calidad superada. Despliegue posible."
