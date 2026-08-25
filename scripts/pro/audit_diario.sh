#!/bin/bash
# Auditoría diaria URA — entorno + tests + informe clasificado.
# NO auto-arregla. Solo genera informe en docs/udo/pendientes/.
# Uso: ./scripts/pro/audit_diario.sh
# Cron sugerido: 0 9 * * * cd ~/URA/ura_ia_1972 && ./scripts/pro/audit_diario.sh

set -uo pipefail
cd "$(dirname "$0")/../.."
RAIZ="$(pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FECHA=$(date +%Y-%m-%d)
LOG="/tmp/pytest_diario_${TIMESTAMP}.log"
ENTORNO="/tmp/ura_entorno_real_$(date +%Y%m%d).json"

echo "[audit] Inicio: $(date)"

# 1. Escanear entorno
if [ -x "$RAIZ/scripts/pro/escanear_entorno.sh" ]; then
    "$RAIZ/scripts/pro/escanear_entorno.sh" "$ENTORNO" > /dev/null 2>&1
    echo "[audit] Entorno escaneado: $ENTORNO"
else
    echo "[audit] WARN: escanear_entorno.sh no existe"
    echo "{}" > "$ENTORNO"
fi

# 2. Ejecutar tests (solo si collect-only está limpio)
if python3 -m pytest --collect-only -q > /dev/null 2>&1; then
    echo "[audit] Ejecutando pytest (timeout 1800s)..."
    timeout 1800 python3 -m pytest tests/ --tb=line --reruns=1 -q 2>&1 | tee "$LOG"
    RC=$?
else
    echo "[audit] ERROR: Tests no pueden colectarse. Abortar." | tee "$LOG"
    exit 1
fi

# 3. Clasificar fallos
if [ -f "$RAIZ/scripts/pro/parse_pytest_results.py" ]; then
    python3 "$RAIZ/scripts/pro/parse_pytest_results.py" --log "$LOG" --entorno "$ENTORNO" --fecha "$FECHA"
    RC_PARSE=$?
else
    echo "[audit] WARN: parse_pytest_results.py no existe"
    RC_PARSE=0
fi

# 4. Alerta activa si hay criticos
if [ "$RC_PARSE" -ne 0 ]; then
    if ! grep -q "🔴" "$RAIZ/docs/udo/pendientes/TEST_AUDIT_${FECHA}.md" 2>/dev/null; then
        echo "⚠️  Hay fallos/desfases en la auditoría de $FECHA. Revisar docs/udo/pendientes/." | tee "$RAIZ/docs/udo/pendientes/ALERTA_ACTIVA.md"
    fi
fi

echo "[audit] Fin: $(date). Exit pytest=$RC parse=$RC_PARSE"
exit $(( RC != 0 || RC_PARSE != 0 ))
