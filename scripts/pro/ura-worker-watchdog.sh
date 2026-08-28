#!/bin/bash
# ura-worker-watchdog.sh
# Watchdog del worker URA (Mac). Reinicia el LaunchAgent com.ura.worker si:
#   1. El proceso worker no existe (muerte limpia — aunque KeepAlive deberia bastar)
#   2. El proceso existe pero lleva mas de WORKER_STALE_SEC sin actividad en el log (colgado)
#
# Ejecutar via launchd (StartInterval) cada 2 min. No toca la DB ni el codigo.

set -u
LOG=/tmp/ura-worker-watchdog.log
WORKER_LOG=/tmp/ura-worker-mac.log
STALE_SEC=${WORKER_STALE_SEC:-300}
PLIST="$HOME/Library/LaunchAgents/com.ura.worker.plist"
UID_NUM=$(id -u)

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"; }

worker_pid() {
	pgrep -f "motor.orchestration.worker --node-id mac" | head -1 || true
}

restart_worker() {
	launchctl bootout "gui/$UID_NUM/com.ura.worker" 2>/dev/null
	sleep 1
	launchctl bootstrap "gui/$UID_NUM" "$PLIST" 2>>"$LOG"
	log "restart_worker: LaunchAgent reiniciado"
}

pid=$(worker_pid)
if [ -z "$pid" ]; then
	log "no hay proceso worker -> reiniciando"
	restart_worker
	exit 0
fi

# Proceso vivo: comprobar actividad reciente del log
if [ -f "$WORKER_LOG" ]; then
	last_ts=$(stat -f "%m" "$WORKER_LOG" 2>/dev/null || stat -c "%Y" "$WORKER_LOG" 2>/dev/null)
	now=$(date +%s)
	if [ -n "$last_ts" ] && [ $((now - last_ts)) -gt "$STALE_SEC" ]; then
		log "worker PID=$pid colgado (log sin cambios ${STALE_SEC}s) -> reiniciando"
		restart_worker
		exit 0
	fi
fi

log "ok: worker PID=$pid activo"
exit 0
