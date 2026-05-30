#!/bin/bash
set -euo pipefail
# vigilancia/orquestar.sh — Orquestador del dominio de Vigilancia
MALETA="$1"; INFORMES="$2"; TS="$3"
for b in "buzo_camaras.sh"; do
    SCRIPT="${HOME}/URA/ura_ia_1972/vigilancia/${b}"
    [ -f "$SCRIPT" ] && timeout 60 bash "$SCRIPT" "$MALETA" "${INFORMES}/hallazgos_vigilancia_${TS}.json" 2>/tmp/ura_errors_vigilancia.log &
done
wait 2>/dev/null || true
