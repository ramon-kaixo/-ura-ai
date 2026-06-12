#!/bin/bash
# URA Hetzner Watchdog — Monitoriza hetzner-escudo desde ASUS
HETZNER_PUBLIC="178.105.81.83"
LOG="/home/ramon/URA/logs/hetzner_watchdog.log"
DISK_WARN=85; DISK_CRIT=92
FAIL_LOG="/tmp/hetzner_fail_count"; MAX_FAILS=3
HCLOUD_TOKEN="${HCLOUD_TOKEN:-REMOVED_HCLOUD_TOKEN}"
SERVER_ID=131473982

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

log "=== Hetzner Watchdog ==="

if ! timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no root@"$HETZNER_PUBLIC" "uptime" >> "$LOG" 2>&1; then
  FAILS=$(cat "$FAIL_LOG" 2>/dev/null || echo 0)
  FAILS=$((FAILS + 1))
  echo "$FAILS" > "$FAIL_LOG"
  log "SSH FAIL #${FAILS}/${MAX_FAILS}"
  if [ "$FAILS" -ge "$MAX_FAILS" ]; then
    log "Power cycle forzado (API reset)"
    curl -s -X POST -H "Authorization: Bearer $HCLOUD_TOKEN" \
      "https://api.hetzner.cloud/v1/servers/$SERVER_ID/actions/reset" >> "$LOG" 2>&1
    echo 0 > "$FAIL_LOG"
  fi
  exit 1
fi
echo 0 > "$FAIL_LOG"

DISK_USAGE=$(ssh root@"$HETZNER_PUBLIC" "df / | tail -1 | awk '{print \$5}' | tr -d '%'" 2>/dev/null)
if [ -n "$DISK_USAGE" ] && [ "$DISK_USAGE" -gt "$DISK_CRIT" ]; then
  log "CRITICO ${DISK_USAGE}% - cleanup remoto"
  ssh root@"$HETZNER_PUBLIC" "/usr/local/bin/cleanup-disk.sh" >> "$LOG" 2>&1
elif [ -n "$DISK_USAGE" ] && [ "$DISK_USAGE" -gt "$DISK_WARN" ]; then
  log "ALTO ${DISK_USAGE}%"
else
  log "OK ${DISK_USAGE:-?}%"
fi

CONT=$(ssh root@"$HETZNER_PUBLIC" "docker ps --format '{{.Names}}'" 2>/dev/null)
log "Contenedores: $(echo "$CONT" | tr '\n' ' ')"
log "=== Fin ==="
