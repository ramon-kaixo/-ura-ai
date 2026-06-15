#!/bin/bash
# URA Hetzner Watchdog — solo monitorización, cero reparación automática
# Ejecuta health check contra hetzner-escudo y escribe estado_alemania.json
# Logs estructurados a stdout/stderr para journald
set -euo pipefail

HETZNER_HOST="100.78.49.106"
SSH_USER="ramon_admin"
SSH_KEY="$HOME/.ssh/id_ura_watchdog"
SSH_BASE="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15"
STATUS_FILE="/home/ramon/URA/ura_ia_1972/deploy/estado_alemania.json"
DISK_WARN=85; DISK_CRIT=92
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

log() { echo "{\"ts\":\"$NOW\",\"component\":\"hetzner_watchdog\",\"event\":\"$1\",\"detail\":${2:-null}}"; }

if OUTPUT=$($SSH_BASE "$SSH_USER@$HETZNER_HOST" "" 2>&1); then
  DISK_USAGE=$(echo "$OUTPUT" | sed -n 's/^DISK://p')
  UPTIME=$(echo "$OUTPUT" | sed -n 's/^UPTIME://p')
  CONTAINERS=$(echo "$OUTPUT" | sed -n 's/^CONTAINERS://p')

  DISK_VAL=${DISK_USAGE:-0}
  if [ "$DISK_VAL" -gt "$DISK_CRIT" ]; then
    log "disk_critical" "{\"disk\":$DISK_VAL,\"threshold\":$DISK_CRIT}"
  elif [ "$DISK_VAL" -gt "$DISK_WARN" ]; then
    log "disk_warning" "{\"disk\":$DISK_VAL,\"threshold\":$DISK_WARN}"
  fi

  STATUS="UP"
  DETAIL="{\"uptime\":\"${UPTIME:-?}\",\"disk\":${DISK_USAGE:-null},\"containers\":\"${CONTAINERS:-ninguno}\"}"
  log "up" "$DETAIL"
else
  STATUS="DOWN"
  DETAIL="{\"error\":\"$(echo "$OUTPUT" | head -1 | tr -d '"')\"}"
  log "down" "$DETAIL"
fi

cat > "$STATUS_FILE" <<EOF2
{
  "ts": "$NOW",
  "global": "$STATUS",
  "ip_publica": "178.105.81.83",
  "ip_tailscale": "100.78.49.106",
  "publica": $( [ "$STATUS" = "UP" ] && echo '"ok"' || echo '"caido"' ),
  "tailscale": $( [ "$STATUS" = "UP" ] && echo '"ok"' || echo '"caido"' ),
  "detalle": $DETAIL
}
EOF2
