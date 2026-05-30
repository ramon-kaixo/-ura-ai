#!/bin/bash
# Sandbox de Aprendizaje — modo bajo demanda
MODE="${2:-on-demand}"
LOG="$HOME/URA/ura_ia_1972/logs/aprendizaje_sandbox.log"
mkdir -p "$(dirname "$LOG")"
echo "[$(date)] 🧠 Activado modo: $MODE" >> "$LOG"
echo "🧠 Sandbox de Aprendizaje: petición registrada en $LOG"
