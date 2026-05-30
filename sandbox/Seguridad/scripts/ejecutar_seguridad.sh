#!/bin/bash
LOG="$(dirname "$0")/../logs/seguridad_$(date +%Y%m%d_%H%M).log"
echo "[$(date)] Iniciando ciclo de Seguridad..." | tee -a "$LOG"
if command -v bandit &>/dev/null; then
    bandit -r ~/URA/ura_ia_1972 -x .venv,__pycache__,archive -f json -o "$(dirname "$0")/../auditoria/bandit_$(date +%Y%m%d).json" 2>/dev/null
    echo "  [OK] Bandit ejecutado" | tee -a "$LOG"
else
    echo "  [SKIP] bandit no instalado" | tee -a "$LOG"
fi
if command -v pip-audit &>/dev/null; then
    cd ~/URA/ura_ia_1972 && source .venv/bin/activate && pip-audit --format json > "$(dirname "$0")/../auditoria/pip_audit_$(date +%Y%m%d).json" 2>/dev/null
    echo "  [OK] pip-audit ejecutado" | tee -a "$LOG"
else
    echo "  [SKIP] pip-audit no instalado" | tee -a "$LOG"
fi
for f in ~/URA/ura_ia_1972/.env ~/.ssh/id_*; do
    if [ -f "$f" ]; then
        perms=$(stat -f "%Lp" "$f" 2>/dev/null || stat -c "%a" "$f" 2>/dev/null)
        echo "  $f → $perms" | tee -a "$LOG"
    fi
done
echo "[$(date)] Ciclo de Seguridad completado" | tee -a "$LOG"
