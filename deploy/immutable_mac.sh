#!/bin/bash
# ============================================================
# immutable_mac.sh — Protocolo de Inmutabilidad Mac
# Gestiona flags uchg en ~/URA/* para impedir ediciones directas.
# ============================================================

URA_DIR="${URA_ROOT:-/Users/ramonesnaola/URA}"
LOG_FILE="$URA_DIR/logs/immutable_mac.log"
LOCK_STATE="$URA_DIR/.URA_IMMUTABLE_STATE"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date)] $1" >> "$LOG_FILE"
    echo "$1"
}

lock_all() {
    log "Bloqueando recursivamente ~/URA/ con chflags uchg..."
    # Bloquear recursivamente excluyendo archivos de estado, logs, backups, data y .git
    find "$URA_DIR" ! -name '.URA_IMMUTABLE_STATE' ! -name '.URA_LOCKED' \
        ! -path "$URA_DIR/logs" ! -path "$URA_DIR/logs/*" \
        ! -path "$URA_DIR/backups_gx10" ! -path "$URA_DIR/backups_gx10/*" \
        ! -path "$URA_DIR/data" ! -path "$URA_DIR/data/*" \
        ! -path "$URA_DIR/.git" ! -path "$URA_DIR/.git/*" \
        -exec chflags uchg {} \; 2>/dev/null || true
    echo "LOCKED" > "$LOCK_STATE"
    chflags nouchg "$LOCK_STATE" 2>/dev/null
    log "OK: ~/URA/ bloqueado recursivamente (chflags uchg)"
    echo ""
    echo "~/URA/ BLOQUEADO RECURSIVAMENTE"
    echo "Para desbloquear: bash $0 unlock"
    echo "Para git: bash $0 git-unlock <repo>"
}

unlock_all() {
    log "Desbloqueando recursivamente ~/URA/ con chflags nouchg..."
    chflags -R nouchg "$URA_DIR" 2>/dev/null || true
    echo "UNLOCKED" > "$LOCK_STATE"
    log "OK: ~/URA/ desbloqueado recursivamente"
    echo ""
    echo "~/URA/ DESBLOQUEADO"
}

git_unlock() {
    local repo="$1"
    if [ -z "$repo" ]; then
        echo "Uso: $0 git-unlock <ruta-repo>"
        exit 1
    fi
    
    log "Desbloqueando recursivamente para git: $repo"
    chflags -R nouchg "$repo" 2>/dev/null || true
    echo "UNLOCKED_FOR_GIT" > "$LOCK_STATE"
    echo "Repo desbloqueado para operación git"
    echo "IMPORTANTE: Re-bloquear después con: bash $0 git-relock <ruta-repo>"
}

git_relock() {
    local repo="$1"
    if [ -z "$repo" ]; then
        echo "Uso: $0 git-relock <ruta-repo>"
        exit 1
    fi
    
    log "Re-bloqueando recursivamente después de git: $repo"
    find "$repo" ! -path "$repo/.git" ! -path "$repo/.git/*" \
         -exec chflags uchg {} \; 2>/dev/null || true
    echo "LOCKED" > "$LOCK_STATE"
    echo "Repo re-bloqueado"
}

status() {
    if [ -f "$LOCK_STATE" ]; then
        STATE=$(cat "$LOCK_STATE")
    else
        STATE="UNKNOWN"
    fi
    
    echo "=== Estado de Inmutabilidad ==="
    echo "Estado: $STATE"
    echo ""
    
    # Verificar flags en archivos clave
    echo "Verificación de flags en archivos clave:"
    local total=0
    local locked=0
    while IFS= read -r -d '' f; do
        ((total++))
        if ls -ldO "$f" 2>/dev/null | grep -q 'uchg'; then
            ((locked++))
        fi
    done < <(find "$URA_DIR/ura_ia_1972" -maxdepth 2 -type f -print0 2>/dev/null)
    echo "  Archivos en ura_ia_1972/: $locked/$total con uchg"
}

case "$1" in
    lock)
        lock_all
        ;;
    unlock)
        unlock_all
        ;;
    git-unlock)
        git_unlock "$2"
        ;;
    git-relock)
        git_relock "$2"
        ;;
    status)
        status
        ;;
    *)
        echo "Uso: $0 {lock|unlock|git-unlock <repo>|git-relock <repo>|status}"
        echo ""
        echo "  lock          - Bloquea ~/URA/* (chflags uchg)"
        echo "  unlock        - Desbloquea ~/URA/* (chflags nouchg)"
        echo "  git-unlock    - Desbloquea temporalmente para git"
        echo "  git-relock    - Re-bloquea después de git"
        echo "  status        - Muestra estado actual"
        exit 1
        ;;
esac
