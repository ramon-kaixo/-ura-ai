#!/bin/bash
set -euo pipefail
# buzo_vigilancia.sh — Monitoriza la salud de Frigate
MALETA="$1"; OUTPUT="$2"
FRIGATE_URL="${FRIGATE_URL:-http://10.164.1.99:5000}"
HALLAZGOS="["

# Verificar Frigate
if curl -s --max-time 5 "${FRIGATE_URL}/api/stats" >/dev/null 2>&1; then
    HALLAZGOS+="{\"buzo\":\"vigilancia\",\"servicio\":\"frigate\",\"estado\":\"ok\"},"
else
    HALLAZGOS+="{\"buzo\":\"vigilancia\",\"servicio\":\"frigate\",\"estado\":\"caido\"},"
fi

# Espacio en disco de grabaciones
DISCO=$(df -h /storage 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo 0)
if [ "$DISCO" -gt 80 ]; then
    HALLAZGOS+="{\"buzo\":\"vigilancia\",\"alerta\":\"disco\",\"uso\":${DISCO},\"mensaje\":\"Almacenamiento > 80%\"},"
fi

HALLAZGOS="${HALLAZGOS%,}]"
echo "$HALLAZGOS" > "$OUTPUT"
echo "✅ Buzo de vigilancia completado"
