#!/bin/bash
set -euo pipefail
REPO="${HOME}/URA/ura_ia_1972"
EXPLO="${REPO}/sandbox/Exploracion"
MINI="${EXPLO}/scripts/mini_tuneladora.sh"
REGISTRY="http://127.0.0.1:5100/agents"
LOG="${EXPLO}/exploracion.log"
mkdir -p "$(dirname "$LOG")"

WATCHLIST=("ruff" "bandit" "safety" "autoflake" "vulture" "radon")
source "${REPO}/.venv/bin/activate"

for PAQUETE in "${WATCHLIST[@]}"; do
    echo "[$(date)] Verificando ${PAQUETE}..." >> "$LOG"
    LATEST=$(curl -s --proxy http://localhost:3128 "https://pypi.org/pypi/${PAQUETE}/json" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])" 2>/dev/null || echo "")
    [ -z "$LATEST" ] && echo "⚠️  No se pudo obtener versión" >> "$LOG" && continue
    INSTALLED=$(pip show "$PAQUETE" 2>/dev/null | grep Version | awk '{print $2}')
    if [ "$LATEST" != "${INSTALLED:-}" ]; then
        echo "🆕 ${PAQUETE} ${LATEST} (instalada: ${INSTALLED:-ninguna})" >> "$LOG"
        if bash "$MINI" "$PAQUETE" "$LATEST" 2>/dev/null; then
            echo "✅ ${PAQUETE} ${LATEST} superó pruebas" >> "$LOG"
            pip install --upgrade "$PAQUETE"=="$LATEST" 2>/dev/null
            curl -s -X POST "$REGISTRY" -H "Content-Type: application/json" \
                -d "{\"id\":\"${PAQUETE}_${LATEST}\",\"type\":\"herramienta\",\"ip\":\"0.0.0.0\",\"port\":0,\"last_seen\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > /dev/null
        else
            echo "🔴 ${PAQUETE} ${LATEST} NO superó pruebas" >> "$LOG"
        fi
    else
        echo "✅ ${PAQUETE} ya actualizado (${INSTALLED})" >> "$LOG"
    fi
done
