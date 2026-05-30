#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/tuneladora_pro.log"
echo "🛫 URA Pro (Paralelo) — $(date)" | tee "$LOG"
# Fases 1 y 2 en paralelo
bash "${DIR}/phase1_diagnosis.sh" &>/tmp/pro_phase1.log & PID1=$!
bash "${DIR}/phase2_filter.sh" &>/tmp/pro_phase2.log & PID2=$!
wait $PID1; E1=$?; wait $PID2; E2=$?
[ $E1 -ne 0 ] && bash "${DIR}/phase4_rollback.sh" "1_diagnosis" && exit 1
[ $E2 -ne 0 ] && bash "${DIR}/phase4_rollback.sh" "2_filter" && exit 1
echo "✅ Fases 1+2 paralelas OK" | tee -a "$LOG"
# Fase 3 secuencial
bash "${DIR}/phase3_architecture.sh" 2>&1 | tee -a "$LOG" || { bash "${DIR}/phase4_rollback.sh" "3_architecture"; exit 1; }
# Fase 5: Modo Sistema (modelos + memoria)
bash "${DIR}/../modo_sistema.sh" audit 2>&1 | tee -a "$LOG" || true
echo "✅ URA Pro completado" | tee -a "$LOG"
