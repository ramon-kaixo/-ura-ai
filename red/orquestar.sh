#!/bin/bash
set -euo pipefail
# red/orquestar.sh — Orquestador del dominio de Red
MALETA="$1"; INFORMES="$2"; TS="$3"
DOMINIO="red"
for b in "buzo_red.sh"; do
    SCRIPT="${HOME}/URA/ura_ia_1972/${DOMINIO}/${b}"
    [ -f "$SCRIPT" ] && timeout 60 bash "$SCRIPT" "$MALETA" "${INFORMES}/hallazgos_${DOMINIO}_${TS}.json" 2>/tmp/ura_errors_${DOMINIO}.log &
done
wait 2>/dev/null || true
