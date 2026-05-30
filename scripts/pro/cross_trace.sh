#!/bin/bash
# Cross-Trace — Documenta el paso de código entre Mac y GX10
set -euo pipefail

TRACE_FILE="${HOME}/URA/ura_ia_1972/docs/pro/cross_trace.log"
OPERATION="${1:-unknown}"
STATUS="${2:-unknown}"
MACHINE=$(hostname -s 2>/dev/null || echo "unknown")

{
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)]"
    echo "  maquina: $MACHINE"
    echo "  operacion: $OPERATION"
    echo "  status: $STATUS"
    echo "  commit: $(git rev-parse HEAD 2>/dev/null || echo '?')"
    echo "  rama: $(git branch --show-current 2>/dev/null || echo '?')"
    echo "  ---"
} >> "$TRACE_FILE"

echo "✅ Traza guardada: $OPERATION → $STATUS en $MACHINE"
