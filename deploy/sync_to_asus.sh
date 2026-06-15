#!/bin/bash
# ============================================================
# sync_to_asus.sh — Sync automático Mac → ASUS
# PRE-FLIGHT VALIDATION OBLIGATORIA: Tests deben pasar.
# Si falla 1 test, el rsync se ABORTA. No se sube nada imperfecto.
# GESTIÓN INTELIGENTE DE INMUTABILIDAD: Desbloquea temporalmente.
# ============================================================
set -e

MAC_DIR="/Users/ramonesnaola/URA/ura_ia_1972"
ASUS_HOST="ramon@10.164.1.99"
ASUS_DIR="/home/ramon/URA/ura_ia_1972"
VALIDATE_SCRIPT="$MAC_DIR/deploy/validate_change.sh"
IMMUTABLE_SCRIPT="$MAC_DIR/deploy/immutable_mac.sh"
LOG_FILE="$MAC_DIR/logs/sync_to_asus.log"
LOCK_STATE="$MAC_DIR/.URA_IMMUTABLE_STATE"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date)] $1" >> "$LOG_FILE"
    echo "$1"
}

abort() {
    log "ABORTADO: $1"
    # Rollback: re-bloquear si estaba bloqueado
    if [ "$WAS_LOCKED" = "true" ]; then
        log "ROLLBACK: Re-bloqueando Mac después de fallo..."
        bash "$IMMUTABLE_SCRIPT" git-relock "$MAC_DIR" >> "$LOG_FILE" 2>&1 || true
    fi
    exit 1
}

# ============================================================
# PRE-FLIGHT: Validación de 139 tests (OBLIGATORIO)
# ============================================================
log "=== PRE-FLIGHT VALIDATION ==="
log "Ejecutando 139 tests ANTES de sincronizar..."

if bash "$VALIDATE_SCRIPT" "$MAC_DIR" > /dev/null 2>&1; then
    log "PRE-FLIGHT OK: 139/139 tests pasaron"
else
    # Mostrar qué falló
    log "PRE-FLIGHT FALLÓ:"
    bash "$VALIDATE_SCRIPT" "$MAC_DIR" 2>&1 | grep "✗" >> "$LOG_FILE"
    abort "Tests fallaron. NADA se sincroniza hasta que todo pase."
fi

# ============================================================
# Verificar que ASUS es alcanzable (check robusto)
# ============================================================
# Intento 1: ping rápido
if ! ping -c 1 -W 2 10.164.1.99 >/dev/null 2>&1; then
    log "WARN: Ping rápido falló, intentando SSH check..."
    # Intento 2: SSH check (más tolerante)
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$ASUS_HOST" "echo ok" >/dev/null 2>&1; then
        abort "ASUS no alcanzable (10.164.1.99) - ni ping ni SSH responden"
    fi
    log "OK: SSH check pasó (ping falló pero SSH funciona)"
fi

# ============================================================
# GESTIÓN INTELIGENTE DE INMUTABILIDAD
# ============================================================
WAS_LOCKED="false"
if [ -f "$LOCK_STATE" ] && [ "$(cat "$LOCK_STATE")" = "LOCKED" ]; then
    WAS_LOCKED="true"
    log "Mac está en modo inmutable (LOCKED)"
    log "Desbloqueando temporalmente para rsync..."
    bash "$IMMUTABLE_SCRIPT" git-unlock "$MAC_DIR" >> "$LOG_FILE" 2>&1 || abort "No se pudo desbloquear Mac"
    log "Mac desbloqueado temporalmente"
else
    log "Mac NO está en modo inmutable (UNLOCKED)"
fi

# ============================================================
# RSYNC: La sync definitiva
# ============================================================
log "=== RSYNC Mac → ASUS ==="
BWLIMIT=${URA_BWLIMIT:-0}  # 0 = unlimited; set via env for WiFi
rsync -avz --delete --delete-after --force \
    ${BWLIMIT:+--bwlimit=$BWLIMIT} \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    --exclude=".git" \
    --exclude="node_modules" \
    --exclude="*.log" \
    --exclude="data/" \
    --exclude=".URA_LOCKED" \
    --exclude=".URA_IMMUTABLE_STATE" \
    --exclude="deploy/immutable_mac.sh" \
    --exclude="scripts/manual_tests" \
    --exclude="scripts/GX10" \
    --exclude=".venv" \
    --exclude="motor/" \
    --exclude="deploy/estado_*.json" \
    --exclude="deploy/diagnostico.json" \
    --exclude=".nervioso" \
    --exclude=".auditor_logs" \
    --exclude=".ruff_cache" \
    --exclude="logs/estibadora" \
    --exclude="agents/vocabulario" \
    --exclude="agents/seguridad" \
    --exclude="agents/mantenimiento" \
    --exclude="agents/investigacion" \
    --exclude="agents/finanzas" \
    --exclude="agents/comunicacion" \
    --exclude="core/weather" \
    --exclude="core/vocabulario" \
    --exclude="core/vision" \
    --exclude="core/validadores" \
    --exclude="core/ui" \
    --exclude="core/threads" \
    --exclude="core/services" \
    --exclude="core/security" \
    --exclude="core/repair" \
    --exclude="core/orchestrator" \
    --exclude="core/nodes" \
    --exclude="core/memory" \
    --exclude="core/integraciones" \
    --exclude="core/indexing" \
    --exclude="core/handlers" \
    --exclude="core/feedback" \
    --exclude="core/federated" \
    --exclude="core/discovery" \
    --exclude="core/connectors" \
    --exclude="core/confidence" \
    --exclude="core/code_agents" \
    --exclude="core/buscadores" \
    --exclude="core/agents" \
    --exclude="sandbox" \
    --exclude="knowledge" \
    --exclude="connectors" \
    --exclude="benchmarks" \
    --exclude=".opencode" \
    --exclude=".config/opencode" \
    "$MAC_DIR/" "$ASUS_HOST:$ASUS_DIR/" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    abort "rsync falló (status $?)"
fi

log "RSYNC OK: Archivos transferidos"

# ============================================================
# RE-BLOQUEAR si estaba bloqueado
# ============================================================
if [ "$WAS_LOCKED" = "true" ]; then
    log "Re-bloqueando Mac después de sync exitoso..."
    bash "$IMMUTABLE_SCRIPT" git-relock "$MAC_DIR" >> "$LOG_FILE" 2>&1 || log "WARN: No se pudo re-bloquear Mac"
    log "Mac re-bloqueado"
fi

# ============================================================
# POST-FLIGHT: Verificar tests en ASUS
# ============================================================
log "=== POST-FLIGHT: Verificación en ASUS ==="
POST_RESULT=$(ssh "$ASUS_HOST" "cd $ASUS_DIR && python3 tests/test_unit.py 2>&1 | tail -3" 2>&1)
echo "$POST_RESULT" >> "$LOG_FILE"

if echo "$POST_RESULT" | grep -q "PASS"; then
    log "POST-FLIGHT OK: Tests en ASUS pasaron"
    log "=== SYNC COMPLETADO EXITOSAMENTE ==="
else
    log "POST-FLIGHT WARN: Tests en ASUS dieron resultado inesperado"
    log "Sync se aplicó pero verificar manualmente"
    # No abortamos porque el sync ya se aplicó
fi

log "=== SYNC FINALIZADO ==="
log "Estado inmutable final: $([ "$WAS_LOCKED" = "true" ] && echo "LOCKED (restaurado)" || echo "UNLOCKED (sin cambios)")"
