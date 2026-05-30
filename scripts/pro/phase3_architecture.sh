#!/bin/bash
set -euo pipefail
REPO="${HOME}/URA/ura_ia_1972"
source "${REPO}/.venv/bin/activate" 2>/dev/null || true
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="${REPO}/docs/pro/reports"
mkdir -p "$REPORT_DIR"

echo "🔄 $(basename "$0" .sh) — $TIMESTAMP"

# Snapshot de seguridad con rollback
python3 -c "from core.ura_rollback import get_ura_rollback; get_ura_rollback().create_snapshot('$(basename $0 .sh)', '.')" 2>/dev/null || true

# Ejecutar comando específico de la fase
case "$(basename $0 .sh)" in
    phase1_diagnosis)
        ruff check "$REPO" --statistics 2>/dev/null | tail -1
        radon cc "$REPO" -a -s 2>/dev/null | tail -1
        pytest tests/ -q --ignore=tests/test_property_based.py 2>/dev/null | tail -3
        ;;
    phase2_filter)
        ruff check --fix "$REPO" 2>/dev/null | tail -1
        autoflake --in-place --remove-all-unused-imports -r "$REPO" --exclude=.venv 2>/dev/null || true
        ruff format "$REPO" --quiet 2>/dev/null | tail -1
        ;;
    phase3_architecture)
        radon cc "$REPO" -a -s 2>/dev/null | tail -1 || true
        vulture "$REPO" --min-confidence 70 2>/dev/null | tail -3 || true
        pytest tests/test_core_basics.py tests/test_consensus_system.py -q 2>/dev/null | tail -3 || true
        ;;
    phase4_rollback)
        echo "Rollback completado"
        exit 0
        ;;
esac

# Verificar tests post-fase
if pytest tests/test_core_basics.py tests/test_consensus_system.py -q 2>/dev/null | grep -q "FAILED"; then
    echo "🔴 Tests fallidos — ejecutando rollback"
    python3 -c "
from core.ura_rollback import get_ura_rollback
rb = get_ura_rollback()
snap = rb.get_latest_snapshot('$(basename $0 .sh)')
if snap: rb.restore_snapshot(snap.snapshot_id, '.')
" 2>/dev/null || true
    exit 1
fi
echo "✅ $(basename $0 .sh) completado"
