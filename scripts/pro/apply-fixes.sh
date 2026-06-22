#!/bin/bash
# apply-fixes.sh — Despliegue seguro de fixes críticos con health-check y rollback
#
# Uso:
#   ./apply-fixes.sh                    → despliega, verifica, revierte si falla
#   ./apply-fixes.sh --rollback         → revierte al backup más reciente
#   ./apply-fixes.sh --status           → muestra estado actual de servicios
#
# Servicios afectados por los fixes:
#   model-router → core/model_router.py, core/inferencia/engine.py
#   snc          → monitor/snc.py
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="/tmp/ura_fixes_backup"
TIMESTAMP=$(date +%s)

SERVICES=("model-router" "snc")
declare -A SERVICE_FILES
SERVICE_FILES["model-router"]="core/model_router.py core/inferencia/engine.py"
SERVICE_FILES["snc"]="monitor/snc.py"

# ── Colores ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()  { echo -e "  ${GREEN}✅${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠️${NC} $1"; }
fail() { echo -e "  ${RED}❌${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

# ── Preflight: sanity checks ──
preflight() {
    echo ""; echo "=== 🩺 Preflight ==="
    local ok=true

    # ¿Ejecutamos como root?
    if [[ $EUID -ne 0 ]]; then
        warn "No eres root — systemctl restart puede fallar sin sudo."
    fi

    # ¿Existen los archivos fuente?
    for svc in "${SERVICES[@]}"; do
        for f in ${SERVICE_FILES[$svc]}; do
            if [[ ! -f "$REPO_DIR/$f" ]]; then
                fail "$f no existe en $REPO_DIR"
                ok=false
            else
                ok "$f presente"
            fi
        done
    done

    # ¿Están los servicios activos?
    for svc in "${SERVICES[@]}"; do
        if systemctl is-active -q "$svc" 2>/dev/null; then
            ok "$svc activo"
        else
            warn "$svc no está activo (estado: $(systemctl is-active "$svc" 2>/dev/null))"
        fi
    done

    # ¿Hay un backup reciente (última hora)?
    local latest=$(ls -t "$BACKUP_DIR" 2>/dev/null | head -1)
    if [[ -n "$latest" ]]; then
        ok "Backup disponible: $BACKUP_DIR/$latest"
    else
        warn "No hay backup previo — se creará uno nuevo."
    fi

    $ok
}

# ── Backup: copia los archivos actuales ──
do_backup() {
    local tag="$1"
    local dest="$BACKUP_DIR/${tag}_${TIMESTAMP}"
    mkdir -p "$dest"
    echo ""; echo "=== 💾 Backup en $dest ==="
    for svc in "${SERVICES[@]}"; do
        for f in ${SERVICE_FILES[$svc]}; do
            local src="$REPO_DIR/$f"
            local dstdir="$dest/$(dirname "$f")"
            mkdir -p "$dstdir"
            cp "$src" "$dstdir/"
            ok "$f respaldado"
        done
    done
    # Backup de tests
    mkdir -p "$dest/tests"
    cp "$REPO_DIR"/tests/test_vram_guard.py "$dest/tests/" 2>/dev/null || true
    cp "$REPO_DIR"/tests/test_inference_engine.py "$dest/tests/" 2>/dev/null || true
    cp "$REPO_DIR"/tests/test_snc_anomalias.py "$dest/tests/" 2>/dev/null || true
    echo "$tag" > "$dest/.tag"
    echo "$dest"
}

# ── Deploy: copia source → destino ──
do_deploy() {
    echo ""; echo "=== 📦 Desplegando fixes ==="
    for svc in "${SERVICES[@]}"; do
        for f in ${SERVICE_FILES[$svc]}; do
            local src="$REPO_DIR/$f"
            local dst="$REPO_DIR/$f"  # mismo path, in-place
            info "$f listo para deploy (in-place en repo)"
        done
    done
    ok "Todos los archivos fuente en su lugar"
}

# ── Health-check de un servicio ──
health_check() {
    local svc="$1"
    local max_wait=10

    # Esperar a que el servicio esté activo
    for ((i=0; i<max_wait; i++)); do
        if systemctl is-active -q "$svc" 2>/dev/null; then
            ok "$svc activo (health-check pasado)"
            return 0
        fi
        sleep 1
    done
    fail "$svc no responde tras $max_wait segundos"
    return 1
}

# ── Aplicar cambios y reiniciar ──
apply_and_restart() {
    local rollback_path="$1"
    echo ""; echo "=== 🔄 Aplicando cambios y reiniciando ==="

    # Orden: snc primero (no tiene dependencias), model-router después
    local svc
    for svc in "snc" "model-router"; do
        info "Reiniciando $svc..."
        if systemctl restart "$svc" 2>/dev/null; then
            if health_check "$svc"; then
                ok "$svc reiniciado y saludable"
            else
                fail "Health-check de $svc falló"
                return 1
            fi
        else
            fail "systemctl restart $svc falló"
            return 1
        fi
    done

    # Health-check adicional: endpoint /health del model-router
    local api_key="${URA_API_KEY:-}"
    if [[ -z "$api_key" ]]; then
        api_key=$(sudo grep "^URA_API_KEY" /etc/ura/secrets.env 2>/dev/null | cut -d= -f2-)
    fi
    if [[ -n "$api_key" ]]; then
        local http_code
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 \
            -H "X-API-KEY: $api_key" http://127.0.0.1:11435/health 2>/dev/null || echo "000")
        if [[ "$http_code" == "200" ]]; then
            ok "model-router /health responde HTTP 200"
        else
            warn "model-router /health responde HTTP $http_code (no crítico)"
        fi
    fi

    return 0
}

# ── Rollback: restaura último backup ──
do_rollback() {
    local latest
    if [[ -n "$1" ]]; then
        latest="$1"
    else
        latest=$(ls -td "$BACKUP_DIR"/*/ 2>/dev/null | head -1)
    fi

    if [[ -z "$latest" ]] || [[ ! -d "$latest" ]]; then
        fail "No hay backup para restaurar en $BACKUP_DIR"
        return 1
    fi

    echo ""; echo "=== ⏪ Rollback desde $latest ==="
    local tag=$(cat "$latest/.tag" 2>/dev/null || echo "desconocido")
    info "Restaurando backup: $tag"

    for svc in "${SERVICES[@]}"; do
        for f in ${SERVICE_FILES[$svc]}; do
            local backup_file="$latest/$f"
            if [[ -f "$backup_file" ]]; then
                cp "$backup_file" "$REPO_DIR/$f"
                ok "$f restaurado"
            else
                warn "$f no encontrado en backup (se salta)"
            fi
        done
    done

    reiniciar_servicios || return 1
    ok "Rollback completado"
}

# ── Reiniciar servicios (post-deploy o post-rollback) ──
reiniciar_servicios() {
    echo ""; echo "=== 🔄 Reiniciando servicios post-cambio ==="
    for svc in "snc" "model-router"; do
        info "Reiniciando $svc..."
        systemctl restart "$svc" 2>/dev/null || { fail "Fallo al reiniciar $svc"; return 1; }
        health_check "$svc" || return 1
    done
}

# ── Status actual ──
show_status() {
    echo ""; echo "=== 📊 Estado de servicios ==="
    for svc in "${SERVICES[@]}"; do
        local state=$(systemctl is-active "$svc" 2>/dev/null || echo "unknown")
        local since=$(systemctl show -p ActiveEnterTimestamp "$svc" 2>/dev/null | cut -d= -f2-)
        echo "  $svc: $state (desde $since)"
    done

    echo ""; echo "=== 📁 Backups disponibles ==="
    if ls -d "$BACKUP_DIR"/*/ &>/dev/null; then
        for d in "$BACKUP_DIR"/*/; do
            local tag=$(cat "$d/.tag" 2>/dev/null || echo "sin tag")
            echo "  $(basename "$d") — $tag"
        done
    else
        echo "  (ninguno)"
    fi
}

# ── Main ──
main() {
    echo "═════════════════════════════════════════════"
    echo "  apply-fixes.sh — Despliegue Seguro"
    echo "  Repositorio: $REPO_DIR"
    echo "═════════════════════════════════════════════"

    case "${1:-}" in
        --rollback)
            do_rollback "$2"
            exit $?
            ;;
        --status)
            show_status
            exit 0
            ;;
        "")
            # Flujo completo
            preflight || { fail "Preflight falló. Abortando."; exit 1; }
            local bp; bp=$(do_backup "pre-deploy")
            do_deploy
            if apply_and_restart "$bp"; then
                ok "Fixes desplegados correctamente"
                info "Para revertir: $0 --rollback $bp"
                exit 0
            else
                fail "Deploy falló. Ejecutando rollback automático..."
                do_rollback "$bp"
                exit 1
            fi
            ;;
        *)
            echo "Uso: $0 [--rollback [path] | --status]"
            exit 1
            ;;
    esac
}

main "$@"
