#!/usr/bin/env bash
# parallel-branch-init.sh — Detecta nodo y crea rama feature/opencode-${NODE_ID}
# Uso: ./scripts/pro/parallel-branch-init.sh
# Requiere: git, hostname (fallback si URA_NODE_ID no está definido)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# --- Detectar nodo ---
if [[ -n "${URA_NODE_ID:-}" ]]; then
    NODE_ID="$URA_NODE_ID"
else
    HOSTNAME_SHORT=$(hostname -s 2>/dev/null || echo "unknown")
    case "$HOSTNAME_SHORT" in
        gx10*|ramon-gx10*) NODE_ID="gx10" ;;
        gx10-web*)         NODE_ID="gx10-web" ;;
        mac*|ramones*)     NODE_ID="mac" ;;
        *)                 NODE_ID="$HOSTNAME_SHORT" ;;
    esac
    echo "[INFO] URA_NODE_ID no definido, inferido: $NODE_ID (hostname: $HOSTNAME_SHORT)"
fi

BRANCH="feature/opencode-${NODE_ID}"
CURRENT=$(git branch --show-current 2>/dev/null || echo "")

if [[ "$CURRENT" == "$BRANCH" ]]; then
    echo "[OK] Ya en rama $BRANCH"
    exit 0
fi

# Fetch latest
git fetch origin main 2>/dev/null || true

# Crear o cambiar a la rama
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    echo "[INFO] Rama $BRANCH ya existe localmente"
    git checkout "$BRANCH"
else
    # Intentar crear desde origin/develop
    if git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
        echo "[INFO] Rama $BRANCH existe en remoto, checkout"
        git checkout -b "$BRANCH" "origin/$BRANCH"
    else
        echo "[INFO] Creando rama nueva $BRANCH desde main"
        git checkout -b "$BRANCH" origin/main 2>/dev/null || git checkout -b "$BRANCH"
    fi
fi

echo "[OK] Nodo: $NODE_ID | Rama: $BRANCH"
echo "$NODE_ID" > "$REPO_ROOT/.opencode/.current-node-id"
