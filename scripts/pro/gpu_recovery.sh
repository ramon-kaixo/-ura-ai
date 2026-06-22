#!/usr/bin/env bash
# ==============================================================================
# gpu_recovery.sh — Recuperación del bug de power cap GB10 (15W/650MHz)
#
# USO:
#   sudo ./gpu_recovery.sh          # Recuperación completa
#   sudo ./gpu_recovery.sh --dry    # Solo diagnóstico, no ejecuta
#   sudo ./gpu_recovery.sh --force  # Fuerza aunque no detecte el bug
# ==============================================================================
set -euo pipefail

LOG_FILE="/var/log/gpu_recovery.log"
URA_ROOT="${URA_ROOT:-/home/ramon/URA/ura_ia_1972}"
GPU_HEALTH="$URA_ROOT/scripts/pro/gpu_health.py"

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# --- Diagnóstico ---
diagnostico() {
    log "=== DIAGNÓSTICO GPU ==="
    if ! command -v nvidia-smi &>/dev/null; then
        log "ERROR: nvidia-smi no encontrado"; return 1
    fi

    local pstate clock power
    pstate=$(nvidia-smi --query-gpu=pstate --format=csv,noheader,nounits 2>/dev/null | tr -d ' ')
    clock=$(nvidia-smi --query-gpu=clocks.current.graphics --format=csv,noheader,nounits 2>/dev/null | tr -d ' ')
    power=$(nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits 2>/dev/null | tr -d ' ')

    log "P-State:    $pstate"
    log "Clock:      $clock MHz"
    log "Power:      ${power}W"

    # Detectar bug
    if [[ "$pstate" =~ ^P(0|2|8|12)$ ]]; then
        log "⛔ P-State anómalo: $pstate"
        return 2
    fi
    if [[ -n "$clock" && "$clock" -lt 1000 ]]; then
        log "⛔ Clock bajo: ${clock}MHz (< 1000)"
        return 2
    fi

    # Verificar health script si existe
    if [[ -f "$GPU_HEALTH" ]]; then
        python3 "$GPU_HEALTH" --json >/dev/null 2>&1
        local rc=$?
        if [[ $rc -eq 2 ]]; then
            log "⛔ GPU_HEALTH detecta BUG"
            return 2
        fi
    fi

    log "✅ GPU aparentemente sana"
    return 0
}

# --- Recuperación ---
recuperar() {
    log "=== INICIANDO RECUPERACIÓN GPU ==="

    # Lock externo (flock -n en crontab / acquire_gpu_lock en tuneladora)
    # No se adquiere lock interno para evitar deadlock con el proceso padre

    # 1. Detener servicios que usan NVIDIA
    log "Deteniendo servicios dependientes..."
    for svc in gdm docker containerd ollama; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            systemctl stop "$svc" 2>/dev/null || true
            log "  ${svc} detenido"
        fi
    done

    # 2. Aislamiento selectivo de procesos caídos de Ollama sin tocar controladores nativos
    log "Matando procesos Ollama/visión en NVIDIA..."
    pkill -9 -f "ollama runner" || true
    pkill -9 -f "llama-vision" || true
    pkill -f "nvidia-smi\|python3.*detector" 2>/dev/null || true
    sleep 2

    # 3. Descargar módulos NVIDIA (orden inverso de dependencia)
    log "Descargando módulos NVIDIA..."
    for mod in nvidia_uvm nvidia_drm nvidia_modeset nvidia; do
        if lsmod | grep -q "^$mod"; then
            rmmod "$mod" 2>/dev/null && log "  ${mod} descargado" || log "  ${mod} no se pudo descargar"
        fi
    done

    # 4. Recargar módulos limpios
    log "Recargando módulos NVIDIA..."
    modprobe nvidia || { log "ERROR: modprobe nvidia falló"; return 1; }
    modprobe nvidia_uvm || { log "ERROR: modprobe nvidia_uvm falló"; return 1; }
    modprobe nvidia_modeset || true
    modprobe nvidia_drm || true
    log "  Módulos recargados"

    # 5. Arrancar servicios
    log "Arrancando servicios..."
    for svc in ollama containerd docker gdm; do
        systemctl start "$svc" 2>/dev/null || true
        log "  ${svc} arrancado"
    done

    # 6. Esperar y verificar
    sleep 3
    log "=== VERIFICACIÓN POST-RECUPERACIÓN ==="
    if diagnostico; then
        log "✅ RECUPERACIÓN EXITOSA"
        return 0
    else
        log "⚠️  RECUPERACIÓN PARCIAL — puede requerir desconexión de corriente"
        return 1
    fi
}

# --- Main ---
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: Este script requiere sudo (se necesita rmmod + systemctl)"
    exit 1
fi

DRY=false; FORCE=false
for arg in "$@"; do
    case "$arg" in --dry) DRY=true;; --force) FORCE=true;; esac
done

diagnostico
DIAG_RC=$?

if [[ $DIAG_RC -ne 2 && "$FORCE" != true ]]; then
    log "No se detecta bug. Usa --force para recuperar igualmente."
    exit 0
fi

if [[ "$DRY" == true ]]; then
    log "Modo dry-run: no se ejecuta recuperación."
    log "Para recuperar: sudo $0"
    exit 0
fi

recuperar
