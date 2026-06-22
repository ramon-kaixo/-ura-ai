#!/bin/bash
# sync_ura.sh — Mantiene sincronizados los directorios URA/ y ura_ia_1972/
# Previene el problema de dualidad de directorios
#
# Uso: ./sync_ura.sh [--dry-run]
set -euo pipefail

PROD="/home/ramon/URA"
REPO="/home/ramon/URA/ura_ia_1972"
DRY_RUN="${1:-}"

echo "=== Sincronizando $PROD ← $REPO ==="

dirs=("core" "scripts" "monitor" "motor" "tests")

for dir in "${dirs[@]}"; do
    if [ "$DRY_RUN" = "--dry-run" ]; then
        echo "  [DRY-RUN] rsync -av --delete $REPO/$dir/ $PROD/$dir/"
    else
        rsync -av --delete "$REPO/$dir/" "$PROD/$dir/" 2>/dev/null
        echo "  ✅ $dir sincronizado"
    fi
done

# Archivos sueltos
for f in "path_setup.py" "agent_hierarchy.py" ".env.secrets.template"; do
    if [ -f "$REPO/$f" ]; then
        if [ "$DRY_RUN" = "--dry-run" ]; then
            echo "  [DRY-RUN] cp $REPO/$f $PROD/$f"
        else
            cp "$REPO/$f" "$PROD/$f"
            echo "  ✅ $f sincronizado"
        fi
    fi
done

echo "=== Sincronización completa ==="