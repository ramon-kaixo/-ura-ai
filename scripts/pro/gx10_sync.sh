#!/bin/bash
# gx10_sync.sh — Para ejecutar en el GX10 cada N horas
set -euo pipefail

REPO="${HOME}/URA/ura_ia_1972"
cd "$REPO"

bash scripts/pro/cross_trace.sh "gx10_sync" "iniciando"

echo "📡 Pull desde Mac..."
git pull origin main --rebase 2>&1 || {
    bash scripts/pro/cross_trace.sh "gx10_sync" "conflicto_git"
    echo "🔴 Conflicto de merge. Revisa el estado de git."
    exit 1
}

echo "🛫 Ejecutando Tuneladora Pro..."
bash scripts/pro/tuneladora_pro.sh 2>&1 || {
    bash scripts/pro/cross_trace.sh "gx10_pro" "fallo"
    echo "🔴 Tuneladora Pro falló en GX10. Revisa logs."
    exit 1
}

bash scripts/pro/cross_trace.sh "gx10_pro" "exito"

echo "📤 Push a origin..."
git push origin main 2>&1 || {
    bash scripts/pro/cross_trace.sh "gx10_push" "fallo"
    echo "🔴 Push falló. Posible conflicto."
    exit 1
}

echo "✅ GX10: sincronización y mantenimiento completados"
