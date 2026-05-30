#!/bin/bash
set -euo pipefail
# gobernanza_datos.sh — Limite de almacenamiento y deteccion de duplicados
KNOWLEDGE_DIR="${HOME}/URA/ura_ia_1972/knowledge"
MEDIA_DIR="${KNOWLEDGE_DIR}/media"
MAX_GB=${MAX_KNOWLEDGE_GB:-50}
DUPLICADOS_LOG="${KNOWLEDGE_DIR}/duplicados.log"
mkdir -p "$MEDIA_DIR"

echo "📊 Gobernanza de datos — $(date)"
echo "   Limite: ${MAX_GB} GB"

# 1. Detectar duplicados por hash
echo "🔍 Buscando duplicados en $MEDIA_DIR..."
find "$MEDIA_DIR" -type f \( -name "*.mp4" -o -name "*.jpg" -o -name "*.png" \) -print0 2>/dev/null | \
    xargs -0 md5 -r 2>/dev/null | sort | uniq -d -w 32 > "$DUPLICADOS_LOG" 2>/dev/null || true

DUPLICADOS=$(wc -l < "$DUPLICADOS_LOG" 2>/dev/null || echo 0)
if [ "$DUPLICADOS" -gt 0 ]; then
    echo "   🗑️  $DUPLICADOS archivos duplicados detectados"
    awk '{print $1}' "$DUPLICADOS_LOG" | sort -u | while read -r hash; do
        [ -n "$hash" ] && find "$MEDIA_DIR" -type f -exec md5 -r {} \; | grep "^$hash" | tail -n +2 | awk '{print $2}' | xargs rm -f 2>/dev/null || true
    done
fi

# 2. Controlar tamano total
echo "📦 Verificando almacenamiento..."
USO_BYTES=$(find "$MEDIA_DIR" -type f -exec stat -f%z {} \; 2>/dev/null | awk '{s+=$1} END {print s}' || echo 0)
USO_GB=$(echo "scale=1; $USO_BYTES / 1073741824" | bc 2>/dev/null || echo 0)

if [ "$(echo "$USO_GB > $MAX_GB" | bc 2>/dev/null)" = "1" ]; then
    echo "   ⚠️  Limite superado (${USO_GB}GB > ${MAX_GB}GB). Eliminando mas antiguos..."
    LIMITE_BYTES=$(echo "$MAX_GB * 1073741824 * 80 / 100" | bc | cut -d. -f1)
    while [ "$(find "$MEDIA_DIR" -type f -exec stat -f%z {} \; | awk '{s+=$1} END {print s}')" -gt "$LIMITE_BYTES" ]; do
        find "$MEDIA_DIR" -type f -exec ls -lt {} \; 2>/dev/null | tail -1 | awk '{print $NF}' | xargs rm -f 2>/dev/null || break
    done
    echo "   ✅ Almacenamiento reducido"
else
    echo "   ✅ Uso actual: ${USO_GB}GB de ${MAX_GB}GB"
fi

echo "✅ Gobernanza de datos completada"
