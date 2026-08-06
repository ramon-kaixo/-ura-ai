#!/bin/bash
set -euo pipefail
echo "═══════════════════════════════════════"
echo "  INFORME FP/FN — $(date)"
echo "═══════════════════════════════════════"
echo ""
bash "$(dirname "$0")/fp_scanner.sh" 2>&1 | grep -v "^$"
echo ""
bash "$(dirname "$0")/fn_scanner.sh" 2>&1 | grep -v "^$"
echo ""
echo "📊 Calibración sugerida:"
python3 -c "
from core.forensic_scribe import suggest_tool_calibration
for t in ['bandit', 'vulture', 'wraith']:
    r = suggest_tool_calibration(t)
    if r:
        print(f'   {r}')
    else:
        print(f'   ✅ {t}: tasa de FP normal')
" 2>/dev/null || echo "   (forensic_scribe no disponible)"
echo ""
echo "═══════════════════════════════════════"
