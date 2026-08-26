#!/usr/bin/env bash
# test_drift.sh — Verifica drift en archivos protegidos
# Ejecutar: ./scripts/pro/test_drift.sh
# Requiere: md5sum (Linux) o md5 (Mac)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HASHES_FILE="$REPO_ROOT/docs/udo/hashes_protegidos.md"
DRIFT=0

log() { echo "[$(date '+%H:%M:%S')] $*"; }
pass() { log "OK: $*"; }
fail() { log "DRIFT: $*"; DRIFT=$((DRIFT + 1)); }

md5_cmd() {
    if command -v md5sum &>/dev/null; then
        md5sum "$1" | awk '{print $1}'
    elif command -v md5 &>/dev/null; then
        md5 -q "$1"
    else
        echo "NO_MD5_TOOL"
    fi
}

# Archivos a verificar
PROTECTED_FILES=(
    "deploy/lildax_config.json"
    "deploy/sync_to_asus.sh"
)

if [[ ! -f "$HASHES_FILE" ]]; then
    log "Creando hashes_protegidos.md con hashes actuales..."
    mkdir -p "$(dirname "$HASHES_FILE")"
    echo "# Hashes de archivos protegidos" > "$HASHES_FILE"
    echo "# Generado automaticamente por test_drift.sh" >> "$HASHES_FILE"
    echo "# Formato: ruta | md5hash" >> "$HASHES_FILE"
    echo "" >> "$HASHES_FILE"
    for f in "${PROTECTED_FILES[@]}"; do
        FULL="$REPO_ROOT/$f"
        if [[ -f "$FULL" ]]; then
            HASH=$(md5_cmd "$FULL")
            echo "$f | $HASH" >> "$HASHES_FILE"
            log "Registrado: $f ($HASH)"
        fi
    done
    pass "Hashes creados. Ejecutar de nuevo para verificar drift."
    exit 0
fi

for f in "${PROTECTED_FILES[@]}"; do
    FULL="$REPO_ROOT/$f"
    if [[ ! -f "$FULL" ]]; then
        log "SKIP: $f no existe"
        continue
    fi
    CURRENT=$(md5_cmd "$FULL")
    STORED=$(grep "^$f" "$HASHES_FILE" 2>/dev/null | head -1 | awk -F'|' '{print $2}' | tr -d ' ')
    if [[ -z "$STORED" ]]; then
        log "WARN: $f no esta en hashes — registrando"
        echo "$f | $CURRENT" >> "$HASHES_FILE"
        continue
    fi
    if [[ "$CURRENT" == "$STORED" ]]; then
        pass "$f sin drift"
    else
        fail "$f drift detectado: esperado=${STORED:0:12} actual=${CURRENT:0:12}"
    fi
done

echo ""
if [[ $DRIFT -eq 0 ]]; then
    log "SIN DRIFT DETECTADO"
else
    log "$DRIFT ARCHIVOS CON DRIFT"
fi
exit $DRIFT
