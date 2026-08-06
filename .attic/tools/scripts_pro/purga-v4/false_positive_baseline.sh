#!/bin/bash
set -euo pipefail
REPO="${HOME}/URA/ura_ia_1972"
BDIR="${REPO}/docs/pro/baseline"
mkdir -p "$BDIR"
echo "📊 Baseline — $(date)"
wraith scan "$REPO" --format json > "${BDIR}/wraith_baseline_$(date +%Y%m%d_%H%M%S).json" 2>/dev/null || echo "⚠️  wraith no disponible"
python3 -c "import slopcheck" &>/dev/null && python3 -m slopcheck "$REPO" --json > "${BDIR}/aislop_baseline_$(date +%Y%m%d_%H%M%S).json" 2>/dev/null || echo "⚠️  ai-slopcheck no disponible"
echo "✅ Baseline guardado"
