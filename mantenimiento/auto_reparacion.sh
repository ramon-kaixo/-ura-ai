#!/bin/bash
# =====================================================================
# PIPELINE DE AUTO-REPARACIÓN DETERMINISTA DE ENTORNO
# =====================================================================
set -e

REPO_DIR=$(pwd)
AUDIT_FAILED=0

echo "[+] Ejecutando auditoría diaria preventiva..."
python3 "$REPO_DIR/ura-audit" || AUDIT_FAILED=1

if [ "$AUDIT_FAILED" == "1" ]; then
    echo "[⚠] Fallo detectado en el entorno. Iniciando acciones de reparacion..."

    # Accion 1: Limpieza de residuos de la sesion previa
    echo "[1/3] Purgando caches y archivos temporales corruptos..."
    rm -rf /tmp/ura-audit-*.json
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    rm -rf .ruff_cache .pytest_cache .mypy_cache 2>/dev/null || true

    # Accion 2: Liberar procesos huerfanos (solo los nuestros)
    echo "[2/3] Liberando procesos huerfanos..."
    fuser -k 4097/tcp 2>/dev/null || true  # GUI Bridge
    fuser -k 4096/tcp 2>/dev/null || true  # Executor API

    # Accion 3: Stash cambios no commiteados (nunca se pierden)
    echo "[3/3] Resguardando cambios locales en git stash..."
    git stash --include-untracked 2>/dev/null || true

    # Segunda vuelta: Validar si la reparacion limpio el entorno
    echo "[+] Re-evaluando el sistema tras la reparacion..."
    if python3 "$REPO_DIR/ura-audit"; then
        echo "[✓] Sistema auto-reparado con exito por el pipeline."
        EXIT_CODE=0
    else
        echo "[✗] Fallo critico persistente. Requiere intervencion manual."
        EXIT_CODE=1
    fi
else
    echo "[✓] El sistema esta limpio. No se requiere intervencion."
    EXIT_CODE=0
fi

# Generar contexto pase lo que pase
bash "$REPO_DIR/ura-contexto"
exit $EXIT_CODE
