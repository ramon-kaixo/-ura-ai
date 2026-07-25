#!/bin/bash
# Sync local edits to ASUS via rsync over SSH + fswatch
# Uso: bash scripts/pro/mac_sync.sh
# Prerrequisitos: brew install fswatch
#                 ssh ramon@10.164.1.99 debe funcionar sin password

set -euo pipefail

ASUS_IP="${1:-10.164.1.99}"
LOCAL="${HOME}/ura_local"
REMOTE="ramon@${ASUS_IP}:/home/ramon/URA/ura_ia_1972"
LOG="${HOME}/ura_sync.log"
PIDFILE="/tmp/ura_mac_sync.pid"
WATCH_DIRS=(
    "${LOCAL}/scripts/pro/tuneladora"
    "${LOCAL}/tests"
)

cleanup() {
    rm -f "$PIDFILE"
    echo "[$(date +%H:%M:%S)] Sync stopped" >> "$LOG"
    exit 0
}

# Single instance check
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Already running (PID $(cat "$PIDFILE")). Use: kill $(cat "$PIDFILE")" >&2
    exit 1
fi
echo "$$" > "$PIDFILE"
trap cleanup SIGTERM SIGINT EXIT

# Initial sync
echo "[$(date +%H:%M:%S)] Starting sync to ${ASUS_IP}..." | tee -a "$LOG"

# Verify SSH
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "ramon@${ASUS_IP}" true 2>/dev/null; then
    echo "ERROR: Cannot SSH to ramon@${ASUS_IP}. Check connectivity and SSH keys." | tee -a "$LOG" >&2
    exit 1
fi

# Verify fswatch
if ! command -v fswatch &>/dev/null; then
    echo "ERROR: fswatch not found. Install: brew install fswatch" | tee -a "$LOG" >&2
    exit 1
fi

# Create local dirs if missing
mkdir -p "${WATCH_DIRS[@]}"

# Initial full sync (pull from ASUS first)
echo "[$(date +%H:%M:%S)] Initial sync from ASUS..." | tee -a "$LOG"
rsync -az --delete -e ssh "${REMOTE}/" "${LOCAL}/" >> "$LOG" 2>&1

echo "[$(date +%H:%M:%S)] Watching ${WATCH_DIRS[*]}..." | tee -a "$LOG"

# Watch and sync
fswatch -o "${WATCH_DIRS[@]}" | while read -r event; do
    echo "[$(date +%H:%M:%S)] Change detected, syncing..." >> "$LOG"
    rsync -az --delete -e ssh "${LOCAL}/" "${REMOTE}/" >> "$LOG" 2>&1
    echo "[$(date +%H:%M:%S)] Sync complete" >> "$LOG"
done
