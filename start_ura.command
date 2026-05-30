#!/bin/bash
#
# Script de Lanzamiento URA - Ejecutable con doble clic
#

# Añadir Homebrew al PATH para Ollama
export PATH="/opt/homebrew/bin:$PATH"

URA_APP_DIR="/Users/ramonesnaola/Desktop/URA_App"
PYTHON_EXE="$URA_APP_DIR/.venv/bin/python3"
MAIN_SCRIPT="$URA_APP_DIR/main_final.py"

# Verificar que Ollama esté corriendo
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Iniciando Ollama..."
    ollama serve > /dev/null 2>&1 &
    sleep 3
fi

# Ejecutar main_final.py
echo "Iniciando URA..."
cd "$URA_APP_DIR"
source "$URA_APP_DIR/.venv/bin/activate"
exec "$PYTHON_EXE" "$MAIN_SCRIPT"
