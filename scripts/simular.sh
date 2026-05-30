#!/bin/bash
set -euo pipefail
# simular.sh — Ejecuta cualquier script en modo simulacion
# Uso: simular.sh scripts/test_buzos.sh

SIM_DIR="/tmp/ura_simulacion"
mkdir -p "$SIM_DIR"

echo "🧪 Modo simulacion: $*"
echo "   Directorio: $SIM_DIR"

# Crear estructura minima para pruebas
mkdir -p "$SIM_DIR/sandbox/Aprendizaje/Enjambre/buzos"
mkdir -p "$SIM_DIR/sandbox/Aprendizaje/Enjambre/informes"
cp -r "$(dirname "$0")/../sandbox/Aprendizaje/Enjambre/buzos/maleta.json" "$SIM_DIR/sandbox/Aprendizaje/Enjambre/buzos/" 2>/dev/null || true

(
    export URA_SIMULACION=true
    export HOME="$SIM_DIR"
    cd "$SIM_DIR"
    "$@" 2>&1 || true
)

echo "   Produccion no afectada"
rm -rf "$SIM_DIR"
