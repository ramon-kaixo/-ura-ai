#!/bin/bash
# agent_heartbeat.sh — Envia heartbeat al Bus cada 60 segundos
# Se ejecuta como servicio en cada maquina de la flota

BUS_URL="${BUS_URL:-http://10.164.1.99:8091}"
AGENT_ID="${HOSTNAME:-$(hostname)}"
AGENT_ROLE="${AGENT_ROLE:-copiloto}"
AGENT_IP="$(tailscale ip -4 2>/dev/null || curl -s ifconfig.me 2>/dev/null || echo '127.0.0.1')"

echo "Heartbeat iniciado para $AGENT_ID (rol: $AGENT_ROLE) -> $BUS_URL"

while true; do
    curl -s -X POST "$BUS_URL/heartbeat" \
        -H "Content-Type: application/json" \
        -d "{\"id\":\"$AGENT_ID\",\"hostname\":\"$AGENT_ID\",\"role\":\"$AGENT_ROLE\",\"ip\":\"$AGENT_IP\"}" \
        > /dev/null 2>&1 || true
    sleep 60
done
