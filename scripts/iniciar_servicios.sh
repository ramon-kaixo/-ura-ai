#!/bin/bash
set -euo pipefail
# Cargar token de seguridad y arrancar servicios URA
TOKEN_FILE="${HOME}/.ura_token"
if [ -f "$TOKEN_FILE" ]; then
    export URA_TOKEN=$(cat "$TOKEN_FILE")
elif [ -z "${URA_TOKEN:-}" ]; then
    export URA_TOKEN="cambiar_token_por_defecto"
    echo "⚠️  URA_TOKEN no configurado. Crea ~/.ura_token con el token."
fi

# Arrancar servicios
for plist in com.coderefine.registry-api com.coderefine.ura-dashboard com.coderefine.buzo-camaras; do
    launchctl setenv URA_TOKEN "$URA_TOKEN"
    launchctl start "$plist" 2>/dev/null || true
done

echo "✅ Servicios URA iniciados con token de seguridad"
