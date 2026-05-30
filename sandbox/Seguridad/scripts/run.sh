#!/bin/bash
# Sandbox de Seguridad — se activa cuando un rodillo bloqueante falla
REASON="${2:-sin motivo}"
LOG="$HOME/URA/ura_ia_1972/logs/seguridad_sandbox.log"
mkdir -p "$(dirname "$LOG")"
echo "[$(date)] 🚨 Activado por: $REASON" >> "$LOG"
echo "🔒 Sandbox de Seguridad: incidencia registrada en $LOG"
