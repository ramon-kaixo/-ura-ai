#!/bin/bash
set -euo pipefail
# rotar_informes.sh — Elimina informes del Enjambre con mas de 90 dias
INFORMES_DIR="${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/informes"
find "$INFORMES_DIR" -name "hallazgos_*.json" -mtime +90 -delete 2>/dev/null || true
echo "🧹 Informes antiguos eliminados"
