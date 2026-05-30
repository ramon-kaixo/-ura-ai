#!/bin/bash
set -euo pipefail
PAQUETE="$1"
VERSION="$2"
EXPLORACION_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROYECTO_PRUEBA="${EXPLORACION_DIR}/proyecto_prueba"

python3 -m venv /tmp/venv_exploracion
source /tmp/venv_exploracion/bin/activate

pip install "$PAQUETE"=="$VERSION" 2>/dev/null

ruff check --fix "$PROYECTO_PRUEBA" 2>/dev/null
python3 -m pytest "$PROYECTO_PRUEBA" -q 2>/dev/null
python3 -m bandit -r "$PROYECTO_PRUEBA" -ll 2>/dev/null

deactivate
rm -rf /tmp/venv_exploracion
