#!/bin/bash
# ura_tailscale_watchdog.sh — Monitor de Tailscale en Mac
# Detecta caídas y notifica al usuario. No intenta reconectar
# (Tailscale en macOS usa IPNExtension, no tailscaled).
# Los peers se consideran OK si tailscale status --json devuelve >=1 online.

TAILSCALE="/opt/homebrew/bin/tailscale"
LOG_FILE="${HOME}/URA/logs/tailscale_watchdog.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

peers_online() {
  local count
  count=$("$TAILSCALE" status --json 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(sum(1 for p in d.get('Peer',{}).values() if p.get('Online')))
except:
    print(0)
" 2>/dev/null)
  echo "${count:-0}" | tr -dc '0-9'
}

failures=0

while true; do
  online=$(peers_online)
  if [ -z "$online" ] || [ "$online" -le 0 ] 2>/dev/null; then
    failures=$((failures + 1))
    log "WARN: 0 peers online (fallo #${failures})"
    if [ "$failures" -ge 3 ]; then
      log "CRITICAL: Tailscale caído (${failures} fallos consecutivos)"
      osascript -e 'display notification "Tailscale caído en Mac" with title "URA Watchdog" subtitle "Red"' 2>/dev/null || true
      failures=0
    fi
  else
    if [ "$failures" -gt 0 ]; then
      log "OK: reconectado tras ${failures} fallos"
      failures=0
    fi
  fi
  sleep 30
done
