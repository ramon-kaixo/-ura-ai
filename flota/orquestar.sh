#!/bin/bash
set -euo pipefail
# flota/orquestar.sh — Orquestador del dominio de Flota
MALETA="$1"; INFORMES="$2"; TS="$3"
for b in "buzo_flota.sh"; do
    SCRIPT="${HOME}/URA/ura_ia_1972/flota/${b}"
    [ -f "$SCRIPT" ] && timeout 60 bash "$SCRIPT" "$MALETA" "${INFORMES}/hallazgos_flota_${TS}.json" 2>/tmp/ura_errors_flota.log &
done
wait 2>/dev/null || true
