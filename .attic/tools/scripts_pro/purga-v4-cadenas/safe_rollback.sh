#!/bin/bash
set -euo pipefail
PHASE="${1:-unknown}"
if [ -f scripts/pro/shadow_git_rollback.sh ]; then
    source scripts/pro/shadow_git_rollback.sh &>/dev/null || true
    if [ -d "/tmp/ura_shadow_git/.git" ]; then
        echo "📦 Shadow Git (primario)..."
        GIT_DIR="/tmp/ura_shadow_git/.git" GIT_WORK_TREE="$HOME/URA/ura_ia_1972" git checkout -- . 2>/dev/null
        exit 0
    fi
fi
echo "⚠️  Shadow Git no disponible. Usando ura_rollback..."
python3 -c "
from core.ura_rollback import get_ura_rollback
rb = get_ura_rollback()
s = rb.get_latest_snapshot('phase${PHASE}')
if s:
    rb.restore_snapshot(s.snapshot_id, '.')
    print('✅ Restaurado')
else:
    print('🔴 Sin snapshot')
" 2>/dev/null || true
