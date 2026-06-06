#!/bin/bash
# ============================================================
# uninstall_opencode.sh — Desinstalación COMPLETA de OpenCode
# Elimina TODOS los archivos, procesos zombies, caches y
# registros launchd de OpenCode en macOS.
#
# Uso: bash deploy/uninstall_opencode.sh [--dry-run]
# ============================================================
set -euo pipefail

DRY_RUN="${1:-}"
LOG_FILE="${HOME}/URA/logs/uninstall_opencode.log"
APP_DIR="/Applications/OpenCode.app"
SUPPORT_DIR="${HOME}/Library/Application Support/ai.opencode.desktop"
CONFIG_DIR="${HOME}/.config/opencode"
CACHE_DIR="${HOME}/Library/Caches/ai.opencode.desktop"
CACHE_SHIPIT="${HOME}/Library/Caches/ai.opencode.desktop.ShipIt"
CACHE_UPDATER="${HOME}/Library/Caches/@opencode-aidesktop-updater"
PREFS="${HOME}/Library/Preferences/ai.opencode.desktop.plist"
PREFS_SHIPIT="${HOME}/Library/Preferences/ByHost/ai.opencode.desktop.ShipIt.*.plist"
HTTP_STORAGE="${HOME}/Library/HTTPStorages/ai.opencode.desktop"
SFILE="${HOME}/Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.ApplicationRecentDocuments/ai.opencode.desktop.sfl4"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

run() {
    if [ -n "$DRY_RUN" ]; then
        log "[DRY-RUN] $*"
    else
        log "EJECUTANDO: $*"
        eval "$@" || log "  ⚠ WARN: falló (no crítico)"
    fi
}

log "=== INICIO DESINSTALACIÓN OPENCODE ==="
log "Dry-run: ${DRY_RUN:-no}"
echo ""

# ────────────────────────────────────────────────────────────
# FASE 1: Matar TODOS los procesos de OpenCode
# ────────────────────────────────────────────────────────────
log "FASE 1: Matando procesos OpenCode..."

run "pkill -9 -f 'OpenCode Helper' 2>/dev/null || true"
run "pkill -9 -f 'OpenCode.app' 2>/dev/null || true"
run "pkill -9 -f 'chrome_crashpad_handler.*opencode' 2>/dev/null || true"
run "pkill -9 -f 'Squirrel.*opencode' 2>/dev/null || true"
sleep 2

# Verificar que no queden procesos
REMAINING=$(ps aux | grep -i opencode | grep -v grep | wc -l | tr -d ' ')
if [ "$REMAINING" -gt 0 ]; then
    log "  ⚠ Quedan ${REMAINING} proceso(s) — intentando kill -9 directo..."
    ps aux | grep -i opencode | grep -v grep | awk '{print $2}' | while read pid; do
        run "kill -9 $pid 2>/dev/null || true"
    done
    sleep 1
fi

# ────────────────────────────────────────────────────────────
# FASE 2: Eliminar ShipIt de launchd
# ────────────────────────────────────────────────────────────
log "FASE 2: Eliminando ShipIt de launchd..."

run "launchctl remove ai.opencode.desktop.ShipIt 2>/dev/null || true"
run "launchctl remove application.ai.opencode.desktop.* 2>/dev/null || true"
sleep 1

# ────────────────────────────────────────────────────────────
# FASE 3: Eliminar SingletonSocket (para romper el ciclo de regeneración)
# ────────────────────────────────────────────────────────────
log "FASE 3: Rompiendo SingletonSocket..."

if [ -L "${SUPPORT_DIR}/SingletonSocket" ]; then
    SOCKET_TARGET=$(readlink "${SUPPORT_DIR}/SingletonSocket" 2>/dev/null || echo "")
    run "rm -f \"$SOCKET_TARGET\" 2>/dev/null || true"
fi
run "rm -f \"${SUPPORT_DIR}/SingletonSocket\" 2>/dev/null || true"
run "rm -f \"${SUPPORT_DIR}/SingletonLock\" 2>/dev/null || true"
run "rm -f \"${SUPPORT_DIR}/SingletonCookie\" 2>/dev/null || true"

# ────────────────────────────────────────────────────────────
# FASE 4: Eliminar archivos de soporte, caches y configs
# ────────────────────────────────────────────────────────────
log "FASE 4: Eliminando archivos de usuario..."

run "rm -rf \"$SUPPORT_DIR\""
run "rm -rf \"$CONFIG_DIR\""
run "rm -rf \"$CACHE_DIR\""
run "rm -rf \"$CACHE_SHIPIT\""
run "rm -rf \"$CACHE_UPDATER\""
run "rm -f \"$PREFS\""
run "rm -f $PREFS_SHIPIT"
run "rm -rf \"$HTTP_STORAGE\""
run "rm -f \"$SFILE\""

# ────────────────────────────────────────────────────────────
# FASE 5: Eliminar la aplicación del /Applications
# ────────────────────────────────────────────────────────────
log "FASE 5: Eliminando app bundle..."

run "rm -rf \"$APP_DIR\""

# ────────────────────────────────────────────────────────────
# FASE 6: Buscar y limpiar .opencode/ en proyectos
# ────────────────────────────────────────────────────────────
log "FASE 6: Buscando .opencode/ en proyectos..."

find "${HOME}" -maxdepth 5 -name ".opencode" -type d 2>/dev/null | while read dir; do
    run "rm -rf \"$dir\""
done

# ────────────────────────────────────────────────────────────
# VERIFICACIÓN FINAL
# ────────────────────────────────────────────────────────────
log ""
log "=== VERIFICACIÓN FINAL ==="

PROCS=$(ps aux | grep -i opencode | grep -v grep | wc -l | tr -d ' ')
FILES_LEFT=0
for path in "$APP_DIR" "$SUPPORT_DIR" "$CONFIG_DIR" "$CACHE_DIR"; do
    if [ -e "$path" ]; then
        FILES_LEFT=$((FILES_LEFT + 1))
        log "  ⚠ AÚN EXISTE: $path"
    fi
done

if [ "$PROCS" -eq 0 ] && [ "$FILES_LEFT" -eq 0 ]; then
    log "✅ OpenCode desinstalado completamente. $PROCS procesos, $FILES_LEFT archivos restantes."
    log "✅ Listo para reinstalar sin problemas."
elif [ "$PROCS" -eq 0 ] && [ "$FILES_LEFT" -gt 0 ]; then
    log "⚠ Parcial: $PROCS procesos, $FILES_LEFT archivos restantes (requiere sudo para algunos)."
    log "   Ejecutar: sudo rm -rf $APP_DIR"
elif [ "$PROCS" -gt 0 ]; then
    log "❌ Crítico: $PROCS procesos aún vivos. Reintentar con:"
    log "   ps aux | grep -i opencode | grep -v grep | awk '{print \$2}' | xargs kill -9"
fi

log ""
log "=== FIN DESINSTALACIÓN ==="
