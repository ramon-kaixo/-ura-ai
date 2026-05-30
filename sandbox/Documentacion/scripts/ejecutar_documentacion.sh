#!/bin/bash
LOG="$(dirname "$0")/../logs/documentacion_$(date +%Y%m%d_%H%M).log"
echo "[$(date)] Iniciando ciclo de Documentacion..." | tee -a "$LOG"
cd ~/URA/ura_ia_1972
source .venv/bin/activate 2>/dev/null || true
echo "  Generando métricas del sistema..." | tee -a "$LOG"
df -h ~ | tail -1 | tee -a "$LOG"
uptime | tee -a "$LOG"
python3 -c "
from core.central_router import get_central_router
r = get_central_router()
s = r.get_status()
print(f'  Agentes activos: {s.get(\"total_intents\", \"?\")}')
print(f'  Shared memory keys: {len(r.list_shared_memory())}')
" 2>/dev/null | tee -a "$LOG" || echo "  [SKIP] central_router no disponible" | tee -a "$LOG"
cd ~/URA/ura_ia_1972
git log --oneline --since="12 hours ago" 2>/dev/null | head -20 | tee -a "$LOG"
echo "  Cambios git registrados" | tee -a "$LOG"
echo "[$(date)] Ciclo de Documentacion completado" | tee -a "$LOG"
