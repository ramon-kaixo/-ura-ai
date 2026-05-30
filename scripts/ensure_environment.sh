#!/bin/bash
# ensure_environment.sh – Autocuracion del entorno Python
# Instala/actualiza dependencias faltantes sin tocar las existentes

URA="${REPO:-$HOME/URA/ura_ia_1972}"
REQ="${URA}/requirements.txt"
[ -f "$REQ" ] || REQ="/opt/ura/requirements.txt"
LOG="${URA}/logs/ensure_env.log"
NOTIFY="/opt/ura/scripts/notificar.sh"
[ -f "$NOTIFY" ] || NOTIFY=""

mkdir -p "$(dirname "$LOG")"
echo "$(date) - Verificando entorno Python..." >> "$LOG"

pip3 install -r "$REQ" --upgrade --quiet --break-system-packages
PIP_OK=$?
pip3 install pipreqs --quiet --break-system-packages 2>/dev/null || true

if [ $PIP_OK -ne 0 ]; then
    echo "ERROR: No se pudo instalar las dependencias" >> "$LOG"
    if [ -n "$NOTIFY" ] && [ -x "$NOTIFY" ]; then
        "$NOTIFY" "Fallo la sincronizacion de dependencias del entorno"
    fi
    exit 1
fi

echo "$(date) - Entorno sincronizado correctamente" >> "$LOG"
