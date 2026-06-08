#!/bin/bash
# =====================================================================
# PIPELINE DE AUTO-REPARACIÓN DETERMINISTA DE ENTORNO
# =====================================================================
set -e

REPO_DIR=$(pwd)
AUDIT_FAILED=0
HISTORICO="$REPO_DIR/mantenimiento/historico_$(hostname).jsonl"

echo "[+] Ejecutando auditoria diaria preventiva..."
python3 "$REPO_DIR/ura-audit" || AUDIT_FAILED=1

if [ "$AUDIT_FAILED" == "1" ]; then
    echo "[⚠] Fallo detectado. Registrando en historico..."
    echo "{\"ts\":\"$(date +%Y-%m-%d)\",\"host\":\"$(hostname)\",\"error\":\"AUDIT_FAILED\",\"modulo\":\"general\",\"reparado\":false}" >> "$HISTORICO"

    echo "[1/3] Purgando caches y archivos temporales..."
    rm -rf /tmp/ura-audit-*.json
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    rm -rf .ruff_cache .pytest_cache .mypy_cache 2>/dev/null || true

    echo "[2/3] Liberando procesos huerfanos..."
    fuser -k 4097/tcp 2>/dev/null || true
    fuser -k 4096/tcp 2>/dev/null || true

    echo "[3/3] Resguardando cambios locales en git stash..."
    git stash --include-untracked 2>/dev/null || true

    echo "[+] Re-evaluando tras reparacion..."
    if python3 "$REPO_DIR/ura-audit"; then
        sed -i '$ s/"reparado":false/"reparado":true/' "$HISTORICO"
        echo "[✓] Sistema auto-reparado con exito."
        EXIT_CODE=0
    else
        echo "[✗] Fallo critico persistente. Requiere intervencion."
        EXIT_CODE=1
    fi
else
    echo "[✓] Sistema limpio."
    EXIT_CODE=0
fi

# Generar contexto y enviar historico pase lo que pase
bash "$REPO_DIR/ura-contexto"
scp "$HISTORICO" ramon@${MAC_TS}:~/REVISIONES_IA/ 2>/dev/null || true
exit $EXIT_CODE
