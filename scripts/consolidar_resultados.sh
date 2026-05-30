#!/bin/bash
# consolidar_resultados.sh - Recoge informes de nodos remotos y los copia al Mac
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
NODOS_DB="${REPO}/data/nodos_conocidos.json"
INFORMES_DIR="${REPO}/sandbox/Aprendizaje/Enjambre/informes"
mkdir -p "$INFORMES_DIR"

if [ ! -f "$NODOS_DB" ]; then
    echo "Base de datos de nodos no encontrada"
    exit 0
fi

jq -r '.nodos[] | select(.desplegado==true) | .id' "$NODOS_DB" 2>/dev/null | while read -r hostname; do
    ip=$(jq -r --arg hn "$hostname" '.nodos[] | select(.id==$hn) | .ip' "$NODOS_DB" 2>/dev/null || true)
    if [ -n "$ip" ]; then
        rsync -avz --timeout=10 "ramon@${ip}:/opt/ura/sandbox/Aprendizaje/Enjambre/informes/" "$INFORMES_DIR/${hostname}/" 2>/dev/null || true
        echo "Informes de $hostname consolidados"
    fi
done

echo "Resultados consolidados"
