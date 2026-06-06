#!/usr/bin/env bash
# ============================================================
# Auto-pull con Rollback — URA GX10
# Ejecutar vía webhook o cron. Hace git pull + test + rollback si falla.
# Guarda hash del último commit bueno para poder volver atrás.
# ============================================================
set -e

REPO_DIR="/home/ramon/URA/ura_ia_1972"
STATE_FILE="/tmp/ura_last_good_commit"
LOCK_FILE="/tmp/ura_auto_pull.lock"

log() { echo "[AUTO-PULL] $(date): $1"; }

# Evitar ejecuciones simultáneas
if [ -f "$LOCK_FILE" ]; then
    log "Ya hay un auto-pull en ejecución (lockfile activo)"
    exit 0
fi
touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

cd "$REPO_DIR"

# Guardar commit actual
CURRENT=$(git rev-parse HEAD 2>/dev/null || echo "none")
log "Commit actual: ${CURRENT:0:8}"

# Pull
log "Ejecutando git pull..."
if ! git pull origin main 2>/dev/null; then
    log "⚠ git pull falló (¿no hay remote?). Continuando con código local."
fi

NEW=$(git rev-parse HEAD 2>/dev/null || echo "none")

if [ "$CURRENT" = "$NEW" ]; then
    log "Sin cambios. Nada que hacer."
    exit 0
fi

log "Nuevo commit: ${NEW:0:8}. Ejecutando tests..."

# Ejecutar tests unitarios
if python3 tests/test_unit.py > /dev/null 2>&1; then
    log "✅ Tests pasaron. Commit ${NEW:0:8} validado."
    echo "$NEW" > "$STATE_FILE"

    # Reiniciar sandbox mejora-continua si existe
    if docker ps --format '{{.Names}}' | grep -q "ura-mejora-continua"; then
        log "Reiniciando mejora-continua..."
        docker restart ura-mejora-continua
    fi

    log "✅ Auto-pull completado con éxito"
    exit 0
else
    log "❌ Tests fallaron. Iniciando rollback a ${CURRENT:0:8}..."

    # Rollback
    git reset --hard "$CURRENT"

    # Restaurar desde último bueno si existe
    if [ -f "$STATE_FILE" ]; then
        LAST_GOOD=$(cat "$STATE_FILE")
        if [ "$LAST_GOOD" != "$CURRENT" ]; then
            log "Rollback adicional a último commit bueno: ${LAST_GOOD:0:8}"
            git reset --hard "$LAST_GOOD"
        fi
    fi

    # Notificar al Mac
    ssh -o ConnectTimeout=2 ramon@10.164.1.26 \
        "osascript -e 'display notification \"Auto-pull falló. Rollback ejecutado.\" with title \"URA GX10\"'" 2>/dev/null || true

    log "⛔ Rollback completado. Sistema en commit seguro."
    exit 1
fi
