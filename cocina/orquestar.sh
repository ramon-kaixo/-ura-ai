#!/bin/bash
set -euo pipefail
# cocina/orquestar.sh — Orquestador del dominio de Cocina
MALETA="$1"; INFORMES="$2"; TS="$3"
for b in "buzo_recetas.sh" "buzo_teoria_culinaria.sh" "buzo_fotos_cocina.sh"; do
    SCRIPT="${HOME}/URA/ura_ia_1972/cocina/${b}"
    [ -f "$SCRIPT" ] && timeout 60 bash "$SCRIPT" "$MALETA" "${INFORMES}/hallazgos_cocina_${TS}.json" 2>/tmp/ura_errors_cocina.log &
done
wait 2>/dev/null || true
