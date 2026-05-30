#!/bin/bash
# auto_finetune_vision.sh - Recopila imagenes de camaras y fine-tune YOLO
set -euo pipefail

REPO="${HOME}/URA/ura_ia_1972"
PY_SCRIPT="${REPO}/core/vision/auto_finetune.py"

mkdir -p "${REPO}/data/vision_dataset/images" "${REPO}/data/vision_dataset/labels"

python3 "$PY_SCRIPT"
echo "Auto fine-tune de vision completado"
