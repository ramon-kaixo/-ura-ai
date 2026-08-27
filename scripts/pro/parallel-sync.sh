#!/usr/bin/env bash
# parallel-sync.sh — Sincronización continua: fetch+rebase+push
# Uso: ./scripts/pro/parallel-sync.sh
# En caso de conflictos, escribe CONFLICT.log y se detiene.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

CONFLICT_LOG="$REPO_ROOT/CONFLICT.log"
CURRENT=$(git branch --show-current 2>/dev/null || echo "")
NODE_ID=$(cat "$REPO_ROOT/.opencode/.current-node-id" 2>/dev/null || echo "unknown")

if [[ "$CURRENT" != feature/opencode-* ]]; then
    echo "[WARN] No estás en una rama feature/opencode-* (actual: $CURRENT). Abortando."
    exit 1
fi

echo "[INFO] Sync de $NODE_ID en rama $CURRENT"

# 1. Fetch
git fetch origin main 2>/dev/null || {
    echo "[WARN] No se pudo hacer fetch. ¿Sin conexión?"
    exit 0
}

# 2. Verificar si hay cambios en develop
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main 2>/dev/null || echo "$LOCAL")
if [[ "$LOCAL" == "$REMOTE" ]]; then
    echo "[OK] develop sin cambios, nada que sincronizar"
    exit 0
fi

# 3. Stash cambios locales si los hay
STASHED=false
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    git stash push -m "parallel-sync-auto-$(date +%s)" 2>/dev/null && STASHED=true
fi

# 4. Rebase
if ! git rebase origin/main 2>/dev/null; then
    echo "[CONFLICT] Conflictos detectados durante rebase"
    git rebase --abort 2>/dev/null || true

    if [[ "$STASHED" == "true" ]]; then
        git stash pop 2>/dev/null || true
    fi

    cat > "$CONFLICT_LOG" <<EOF
CONFLICTO DETECTADO — $(date -u +%Y-%m-%dT%H:%M:%SZ)
Nodo: $NODE_ID
Rama: $CURRENT
Acción requerida: resolver conflictos manualmente y ejecutar: git rebase origin/main
EOF
    echo "[STOP] Revisa $CONFLICT_LOG"
    exit 1
fi

# 5. Push
git push origin HEAD 2>/dev/null || {
    echo "[WARN] Push falló (¿rama nueva en remoto?). Intentando push -u..."
    git push -u origin HEAD 2>/dev/null || echo "[ERROR] Push falló definitivamente"
}

# 6. Restore stash
if [[ "$STASHED" == "true" ]]; then
    git stash pop 2>/dev/null || echo "[WARN] No se pudo restaurar stash"
fi

rm -f "$CONFLICT_LOG"
echo "[OK] $NODE_ID sincronizado en $CURRENT"
