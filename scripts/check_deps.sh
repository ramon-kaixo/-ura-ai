#!/bin/bash
# check_deps.sh – Verifica que todas las importaciones Python tengan sus dependencias instaladas
#
# Uso:
#   SOURCE_DIR=/ruta/al/proyecto scripts/check_deps.sh

set -e

SOURCE_DIR="${SOURCE_DIR:-$HOME/URA/ura_ia_1972}"
REQUIREMENTS="$SOURCE_DIR/requirements.txt"
TEMP_DIR=$(mktemp -d /tmp/ura_deps_XXXXX)

trap 'rm -rf "$TEMP_DIR"' EXIT

echo "=== Creando entorno virtual ==="
python3 -m venv "$TEMP_DIR/venv"
source "$TEMP_DIR/venv/bin/activate"

echo "=== Instalando dependencias ==="
pip install -r "$REQUIREMENTS" --quiet


echo "=== Analizando imports (estático) ==="
SOURCE_DIR="$SOURCE_DIR" python3 "$(dirname "$0")/check_deps.py"
result=$?

if [ $result -eq 0 ]; then
    echo "OK — todas las dependencias estan correctas"
else
    echo "ERROR — faltan dependencias o imports rotos (listados arriba)"
fi

exit $result
