#!/bin/bash
set -euo pipefail
# auto_update.sh — Auto-actualizacion segura de URA
REPO="${HOME}/URA/ura_ia_1972"
BRANCH="${1:-main}"
cd "$REPO" 2>/dev/null || exit 0
[ ! -d ".git" ] && echo "   Sin repositorio git" && exit 0

echo "   🔄 Verificando actualizaciones..."
OLD_HASH=$(git rev-parse HEAD 2>/dev/null || echo "")
git fetch origin "$BRANCH" 2>/dev/null || { echo "   Sin conexion"; exit 0; }
NEW_HASH=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "")
[ "$OLD_HASH" = "$NEW_HASH" ] && echo "   ✅ Ya actualizada" && exit 0

echo "   🆕 ${NEW_HASH:0:7}"
git pull origin "$BRANCH" 2>/dev/null || { echo "   🔴 Conflicto"; exit 1; }

if bash "${REPO}/scripts/test_regression.sh" 2>/dev/null; then
    echo "   ✅ Tests OK. Actualizada."
    bash "${REPO}/scripts/notificar.sh" "URA actualizada a ${NEW_HASH:0:7}" info all 2>/dev/null || true
else
    echo "   🔴 Tests fallidos. Revirtiendo..."
    git reset --hard "$OLD_HASH"
    bash "${REPO}/scripts/notificar.sh" "Actualizacion URA fallida. Revertida." warn all 2>/dev/null || true
    exit 1
fi
