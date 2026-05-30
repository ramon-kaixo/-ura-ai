#!/bin/bash
# sync_requirements.sh – Compara requirements.txt con los imports reales y alerta si hay diferencias
set -e

cd /opt/ura

if ! command -v pipreqs &>/dev/null; then
    echo "pipreqs no instalado. Ejecuta: pip install pipreqs"
    exit 1
fi

echo "Generando requirements.txt a partir del codigo (pipreqs)..."
TEMP_REQ=$(mktemp /tmp/ura_requirements_XXXXX.txt)
trap 'rm -f "$TEMP_REQ"' EXIT

pipreqs . --force --savepath "$TEMP_REQ" > /dev/null 2>&1

if ! diff -q "$TEMP_REQ" requirements.txt > /dev/null; then
    echo "requirements.txt esta desactualizado. Diferencias:"
    diff -u requirements.txt "$TEMP_REQ" | head -20
    echo ""
    echo "Para actualizar requirements.txt, ejecuta:"
    echo "   cp $TEMP_REQ requirements.txt"
    if [ -x /opt/ura/scripts/notificar.sh ]; then
        /opt/ura/scripts/notificar.sh "requirements.txt desactualizado. Ejecuta sync_requirements.sh para actualizar."
    fi
    exit 1
fi

echo "OK — requirements.txt sincronizado con el codigo."
