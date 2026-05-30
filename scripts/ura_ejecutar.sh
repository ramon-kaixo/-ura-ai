#!/bin/bash
# ura_ejecutar.sh — Ejecuta una tarea en un agente especifico o broadcast
# Los agentes empiezan como OBSERVADORES. Solo ejecutan cuando se les llama.
# Uso: bash ura_ejecutar.sh <comando> [destino]
# Ej:  bash ura_ejecutar.sh "estado" "gx10-64c3"
#      bash ura_ejecutar.sh "ls /opt/ura" "broadcast"

set -euo pipefail

COMANDO="${1:-}"
DESTINO="${2:-broadcast}"
BUS_URL="http://10.164.1.99:8091"
REPO="${HOME}/URA/ura_ia_1972"
LOG="${REPO}/logs/ejecutar.log"

[ -z "$COMANDO" ] && echo "Uso: $0 <comando> [destino]" && exit 1

mkdir -p "$(dirname "$LOG")"
echo "=== Ejecutar — $(date) ===" | tee "$LOG"
echo "  Comando: $COMANDO" | tee -a "$LOG"
echo "  Destino: $DESTINO" | tee -a "$LOG"

# Enviar tarea via Bus
curl -s -X POST "$BUS_URL/send" \
    -H "Content-Type: application/json" \
    -d "{\"sender\":\"mac-mini-de-ramon\",\"recipient\":\"$DESTINO\",\"topic\":\"tarea/ejecutar\",\"payload\":\"$COMANDO\",\"priority\":\"normal\"}" \
    > /dev/null 2>&1

echo "  Tarea enviada al Bus" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "Para ver resultados: curl -s $BUS_URL/inbox/mac-mini-de-ramon | python3 -m json.tool" | tee -a "$LOG"
