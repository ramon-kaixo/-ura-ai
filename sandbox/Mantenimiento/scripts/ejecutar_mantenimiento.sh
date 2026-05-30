#!/bin/bash
# Ejecutado por sandbox_orchestrator en ciclo de Mantenimiento
LOG="$(dirname "$0")/../logs/mantenimiento_$(date +%Y%m%d_%H%M).log"
echo "[$(date)] Iniciando ciclo de Mantenimiento..." | tee -a "$LOG"

# 1. Limpiar caches Python
find ~/URA -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "  [OK] Caches Python limpiados" | tee -a "$LOG"

# 2. Limpiar caches pip
pip cache purge 2>/dev/null || true
echo "  [OK] Cache pip purgado" | tee -a "$LOG"

# 3. Optimizar SQLite
for db in $(find ~/URA -name "*.db" -not -path "*/.venv/*" 2>/dev/null); do
    sqlite3 "$db" "VACUUM; REINDEX;" 2>/dev/null || true
done
echo "  [OK] Bases de datos optimizadas" | tee -a "$LOG"

# 4. Rotar logs (comprimir logs > 30 días)
find ~/URA -name "*.log" -mtime +30 -exec gzip {} \; 2>/dev/null || true
echo "  [OK] Logs rotados" | tee -a "$LOG"

# 5. Limpiar temporales
rm -rf /tmp/ura_* 2>/dev/null || true
echo "  [OK] Temporales limpiados" | tee -a "$LOG"

echo "[$(date)] Ciclo de Mantenimiento completado" | tee -a "$LOG"
