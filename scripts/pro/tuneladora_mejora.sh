#!/bin/bash
set -euo pipefail
echo "Tuneladora de Mejora Continua - $(date)"
cd /workspace
ruff check . --fix --quiet
ruff format . --quiet
pytest --quiet || { echo "Tests fallidos. Codigo en cuarentena."; exit 1; }
bandit -r . -ll 2>/dev/null || true
rsync -avz /workspace/ /zona_trabajo/
echo "Codigo promocionado a Mantenimiento"
