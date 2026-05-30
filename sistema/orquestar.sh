#!/bin/bash
set -euo pipefail
# sistema/orquestar.sh — Orquestador del dominio de Sistema
MALETA="$1"; INFORMES="$2"; TS="$3"
for b in "buzo_mac.sh" "buzo_sistema.sh"; do
    SCRIPT="${HOME}/URA/ura_ia_1972/sistema/${b}"
    [ -f "$SCRIPT" ] && timeout 60 bash "$SCRIPT" "$MALETA" "${INFORMES}/hallazgos_sistema_${TS}.json" 2>/tmp/ura_errors_sistema.log &
done
wait 2>/dev/null || true
