#!/bin/bash
# monitoreo_urgente.sh — Guardia de recursos: detecta degradación antes del crash.
# Ejecutar desde crontab de root CADA MINUTO.
# Sin color, sin emoji, sin adornos. Loggea solo acciones.

LOG=/var/log/ura-guardia.log

log() { echo "$(date +%Y-%m-%dT%H:%M:%S) $*" >> "$LOG"; }

# === Leer métricas del sistema ===
iowait=$(awk '/^cpu / {print $13}' /proc/stat 2>/dev/null || echo 0)
ram_total=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 1)
ram_available=$(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null || echo 1)
ram_pct=$(( (ram_total - ram_available) * 100 / ram_total ))
pull_activo=$(pgrep -f "docker pull" >/dev/null && echo 1 || echo 0)

# === Regla 1: iowait > 20% → renice procesos con I/O ===
if [ "$iowait" -gt 20 ] 2>/dev/null; then
    # Renice procesos en estado D (uninterruptible sleep = I/O bound)
    renice_count=$(ps -eo pid,stat --no-headers 2>/dev/null | awk '$2 ~ /^D/ {print $1}' | xargs -r renice -n 19 2>&1 | wc -l)
    log "iowait=$iowait% renice ${renice_count:-0} D-state"
fi

# === Regla 2: RAM > 90% y NO es pull → pausar ura-executor ===
if [ "$ram_pct" -gt 90 ] && [ "$pull_activo" -eq 0 ]; then
    log "RAM=${ram_pct}% STOP ura-executor"
    systemctl kill -s SIGSTOP ura-executor 2>/dev/null || true
    sleep 10

    ram_available2=$(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null || echo 1)
    ram_pct2=$(( (ram_total - ram_available2) * 100 / ram_total ))
    if [ "$ram_pct2" -gt 85 ]; then
        log "RAM=${ram_pct2}% KILL ura-executor (escalado de SIGSTOP)"
        systemctl kill -s SIGKILL ura-executor 2>/dev/null || true
    else
        systemctl kill -s SIGCONT ura-executor 2>/dev/null || true
        log "RAM=${ram_pct2}% CONT ura-executor (pico superado)"
    fi
fi
