#!/usr/bin/env bash
# ============================================================
# Claw Listener — Barrera de seguridad humana en Mac
# Muestra un diálogo osascript requiriendo click para confirmar
# acciones destructivas solicitadas por panic_handler.sh
# ============================================================

TITLE="${1:-PANIC_ALERT}"
MESSAGE="${2:-Accion de emergencia solicitada desde GX10}"

osascript -e "
display dialog \"$MESSAGE\" buttons {\"Cancelar\", \"Autorizar\"} default button \"Cancelar\" with icon caution with title \"$TITLE\"
" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "CONFIRMADO"
    exit 0
else
    echo "CANCELADO"
    exit 1
fi
