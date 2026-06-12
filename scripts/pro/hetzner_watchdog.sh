#!/bin/bash
# URA Hetzner Watchdog
HETZNER_PUBLIC="178.105.81.83"
LOG="/home/ramon/URA/logs/hetzner_watchdog.log"
DISK_WARN=85; DISK_CRIT=92
FAIL_LOG="/tmp/hetzner_fail_count"; MAX_FAILS=3
HCLOUD_TOKEN="REMOVED_HCLOUD_TOKEN"
SERVER_ID=131473982
log() { echo "[$(date "+%Y-%m-%d %H:%M:%S")] $*" >> "$LOG"; }
log "=== Hetzner Watchdog ==="
if ! timeout 15 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no root@"$HETZNER_PUBLIC" "uptime" >> "$LOG" 2>&1; then
  FAILS=$(cat "$FAIL_LOG" 2>/dev/null || echo 0); FAILS=$((FAILS+1)); echo "$FAILS" > "$FAIL_LOG"
  if [ "$FAILS" -ge "$MAX_FAILS" ]; then
    log "Power cycle forzado"
    curl -s -X POST -H "Authorization: Bearer $HCLOUD_TOKEN" \
      "https://api.hetzner.cloud/v1/servers/$SERVER_ID/actions/reset" >> "$LOG" 2>&1
    echo 0 > "$FAIL_LOG"
  fi
  exit 1
fi
echo 0 > "$FAIL_LOG"
DISK=$(ssh root@"$HETZNER_PUBLIC" "df / | tail -1 | awk \"'{print \$5}'" | tr -d %'")
if [ -n "$DISK" ] && [ "$DISK" -gt "$DISK_CRIT" ]; then
  log "CRITICO ${DISK}% - cleanup remoto"
  ssh root@"$HETZNER_PUBLIC" "/usr/local/bin/cleanup-disk.sh" >> "$LOG" 2>&1
elif [ -n "$DISK" ] && [ "$DISK" -gt "$DISK_WARN" ]; then
  log "ALTO ${DISK}%"
else
  log "OK ${DISK}%"
fi
log "=== Fin ==="
