#!/bin/bash
# ============================================================
# lock_mac_folder.sh — Bloqueo de ediciones directas en Mac
# Usa un flag file que la IA respeta.
# Git operations siguen funcionando.
# ============================================================

MAC_DIR="${URA_ROOT:-/Users/ramonesnaola/URA}/ura_ia_1972"
LOCK_FLAG="$MAC_DIR/.URA_LOCKED"
LOCK_LOG="$MAC_DIR/logs/lock_mac_folder.log"

mkdir -p "$(dirname "$LOCK_LOG")"

case "$1" in
    lock)
        touch "$LOCK_FLAG"
        echo "[$(date)] Mac folder marcado como READ-ONLY" >> "$LOCK_LOG"
        echo "Mac folder bloqueado para ediciones directas"
        echo "Git operations siguen funcionando"
        echo "Para desbloquear: bash $0 unlock"
        ;;
    unlock)
        rm -f "$LOCK_FLAG"
        echo "[$(date)] Mac folder desbloqueado" >> "$LOCK_LOG"
        echo "Mac folder desbloqueado"
        ;;
    status)
        if [ -f "$LOCK_FLAG" ]; then
            echo "STATUS: BLOQUEADO"
            echo "La carpeta URA está en modo solo lectura"
            echo "Solo git operations están permitidas"
        else
            echo "STATUS: DESBLOQUEADO"
            echo "La carpeta URA está en modo normal"
        fi
        ;;
    *)
        echo "Uso: $0 {lock|unlock|status}"
        echo ""
        echo "  lock    - Bloquea ediciones directas"
        echo "  unlock  - Desbloquea la carpeta"
        echo "  status  - Muestra el estado actual"
        exit 1
        ;;
esac
