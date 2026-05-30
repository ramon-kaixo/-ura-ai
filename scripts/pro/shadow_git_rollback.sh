#!/bin/bash
set -euo pipefail
SHADOW="/tmp/ura_shadow_git"
shadow_init() {
    rm -rf "$SHADOW"; git init "$SHADOW" &>/dev/null
    GIT_DIR="$SHADOW/.git" GIT_WORK_TREE="$HOME/URA/ura_ia_1972" git add -A &>/dev/null
    GIT_DIR="$SHADOW/.git" GIT_WORK_TREE="$HOME/URA/ura_ia_1972" git commit -m "shadow-$(date -Iseconds)" --allow-empty &>/dev/null
    echo "✅ Shadow git listo en $SHADOW"
}
shadow_rollback() {
    if [ -d "$SHADOW/.git" ]; then
        GIT_DIR="$SHADOW/.git" GIT_WORK_TREE="$HOME/URA/ura_ia_1972" git checkout -- . &>/dev/null
        echo "📦 Rollback desde shadow git"
    else echo "🔴 No hay shadow git"; fi
}
[ "${1:-}" = "--init" ] && shadow_init
[ "${1:-}" = "--rollback" ] && shadow_rollback
