#!/bin/bash
# indexar_manuales_multimodal.sh - Indexa PDF, imagenes y videos en ChromaDB
set -euo pipefail

REPO="${HOME}/URA/ura_ia_1972"
PY_INDEXER="${REPO}/core/indexing/multimodal_indexer.py"

mkdir -p "${REPO}/docs/manuales"

export MANUAL_DIR="${REPO}/docs/manuales"
python3 "$PY_INDEXER"
echo "Indexacion multimodal completada"
