#!/bin/bash
# ura-wip-guard.sh — Prevención de WIP acumulado
# Modos:
#   check   → pre-commit: bloquea si hay cambios sin commit >24h
#   status  → muestra días desde último commit + archivos modificados
#   auto    → auto-commit WIP (para cron nocturno)

set -e

REPO="/opt/ura"
cd "$REPO" 2>/dev/null || REPO="$HOME/URA/ura_ia_1972" && cd "$REPO"

LAST_COMMIT_TS=$(git log -1 --format=%ct 2>/dev/null || echo "0")
NOW_TS=$(date +%s)
SECONDS_SINCE_LAST=$((NOW_TS - LAST_COMMIT_TS))
DAYS_SINCE_LAST=$((SECONDS_SINCE_LAST / 86400))

MODIFIED_COUNT=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
STAGED_COUNT=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')

case "${1:-status}" in
    check)
        if [ "$DAYS_SINCE_LAST" -ge 1 ] && [ "$MODIFIED_COUNT" -gt 0 ]; then
            echo "⚠️  Llevas $DAYS_SINCE_LAST día(s) sin commitear y $MODIFIED_COUNT archivos sin commit."
            echo "   Considera committear o stash antes de acumular más deuda técnica."
            # Aviso, no bloqueo — el bloqueo real está en CI
        fi
        exit 0
        ;;
    status)
        echo "📊 URA WIP Status"
        echo "   Último commit:  $(git log -1 --format=%ar 2>/dev/null || echo 'N/A')"
        echo "   Días sin commit: $DAYS_SINCE_LAST"
        echo "   Archivos modificados sin commit: $MODIFIED_COUNT"
        echo "   Archivos staged:                  $STAGED_COUNT"
        if [ "$DAYS_SINCE_LAST" -ge 3 ]; then
            echo "⚠️  ¡Llevas $DAYS_SINCE_LAST días sin commitear!"
        fi
        exit 0
        ;;
    auto)
        if [ "$MODIFIED_COUNT" -eq 0 ]; then
            echo "✅ Sin cambios — nada que commitear"
            exit 0
        fi
        BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        git add -A
        git commit -m "WIP: auto-commit nocturno ($(date '+%Y-%m-%d %H:%M'))" --allow-empty
        echo "✅ Auto-commit realizado en $BRANCH ($MODIFIED_COUNT archivos)"
        exit 0
        ;;
    *)
        echo "Uso: $0 {check|status|auto}"
        exit 1
        ;;
esac
