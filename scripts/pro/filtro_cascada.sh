#!/bin/bash
# =====================================================================
# filtro_cascada.sh — Gatekeeper (Ahorcador) + Codificador
# Separa grano de paja, marca marketing, envia solo metadatos al Asus
# =====================================================================
set -euo pipefail

ARCHIVO=$1
TIPO_MARKETING=0
LOG="/root/.nervioso/ura_search/filtro_cascada.log"

# 1. Ahorcador (Hard-Gate): Descarte de basura pura
if [[ "$ARCHIVO" =~ (ad|track|pixel|banner|sponsor) ]]; then
    TIPO_MARKETING=1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] MARKETING: $ARCHIVO" >> "$LOG"
elif [ $(stat -c%s "$ARCHIVO" 2>/dev/null || echo 0) -gt 52428800 ]; then
    # Archivo > 50MB y no es marketing = basura. Eliminar.
    rm -f "$ARCHIVO"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BASURA (>50MB): $ARCHIVO eliminado" >> "$LOG"
    exit 0
fi

# 2. Codificador: Generar JSON de metadatos (solo esto viaja al Asus)
FECHA=$(date +%Y)
HASH=$(sha256sum "$ARCHIVO" 2>/dev/null | cut -d' ' -f1)
TAMANO_KB=$(( $(stat -c%s "$ARCHIVO" 2>/dev/null || echo 0) / 1024 ))

cat > "${ARCHIVO}.json" << EOF
{
  "archivo": "$(basename $ARCHIVO)",
  "ruta": "$ARCHIVO",
  "tipo": "$( [ $TIPO_MARKETING -eq 1 ] && echo "MARKETING" || echo "CONTENIDO" )",
  "anio": "${FECHA}",
  "hash": "${HASH}",
  "tamano_kb": ${TAMANO_KB},
  "estilo": "analizando...",
  "timestamp": "$(date -Iseconds)"
}
EOF

echo "[$(date '+%Y-%m-%d %H:%M:%S')] INDEXADO: $ARCHIVO (${TAMANO_KB}KB, $([ $TIPO_MARKETING -eq 1 ] && echo 'MARKETING' || echo 'CONTENIDO'))" >> "$LOG"

# 3. Sincronización ligera: solo el JSON viaja al Asus
rsync -av "${ARCHIVO}.json" root@10.164.1.99:/home/ramon/.nervioso/ura_search/cola/hetzner/metadata/ 2>/dev/null || true
