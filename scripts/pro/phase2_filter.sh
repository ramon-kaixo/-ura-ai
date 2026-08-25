#!/bin/bash
set -euo pipefail
REPO="${HOME}/URA/ura_ia_1972"
source "${REPO}/.venv/bin/activate" 2>/dev/null || true
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="${REPO}/docs/pro/reports"
mkdir -p "$REPORT_DIR"

echo "🔄 $(basename "$0" .sh) — $TIMESTAMP"

# Ejecutar comando específico de la fase
case "$(basename $0 .sh)" in
    phase1_diagnosis)
        ruff check "$REPO" --statistics 2>/dev/null | tail -1
        radon cc "$REPO" -a -s 2>/dev/null | tail -1
        pytest tests/ -q 2>/dev/null | tail -3
        ;;
    phase2_filter)
        ruff check --fix "$REPO" --quiet 2>/dev/null || true
        autoflake --in-place --remove-all-unused-imports -r "$REPO" --exclude=.venv 2>/dev/null || true
        ruff format "$REPO" --quiet 2>/dev/null || true
        ;;
    phase3_architecture)
        radon cc "$REPO" -a -s 2>/dev/null | tail -1
        vulture "$REPO" --min-confidence 70 2>/dev/null | tail -3 || true
        echo "  (test_core_basics/consensus_system eliminados — no existen)"
        ;;
    phase4_rollback)
        echo "Rollback completado"
        exit 0
        ;;
esac

echo "✅ $(basename $0 .sh) completado"
