#!/bin/bash
# ura-fondo-health.sh — Health-check del sistema de revisión autónoma de fondo.
# Reporta en una vista el estado completo del sistema TERM + modo fondo.
# Uso: bash ura-fondo-health.sh  (en la Mac, o vía ssh desde ASUS)

set -u
LOG=/tmp/fondo-wake.log
URL=http://127.0.0.1:8091
REPO=${1:-$HOME/URA/ura_ia_1972}
FONDO_FILE="$REPO/docs/udo/hallazgos-fondo.md"

echo "=== 1. Servidor TERM ==="
if curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$URL/" | grep -q 200; then
    echo "  OK — HTTP 200 en :8091"
else
    echo "  ❌ CAÍDO — sin respuesta en :8091"
fi

echo "=== 2. Watchdog launchd ==="
launchctl list 2>/dev/null | grep -E "opencode-term|fondo-wake" || echo "  ⚠️ jobs no encontrados"

echo "=== 3. Lock del despertador ==="
if [ -d /tmp/fondo-wake.lock ]; then
    PID=$(cat /tmp/fondo-wake.lock/pid 2>/dev/null || echo "?")
    if kill -0 "$PID" 2>/dev/null; then
        echo "  ⚠️ lock ACTIVO (pid=$PID) — run en curso"
    else
        echo "  ❌ lock HUÉRFANO (pid=$PID muerto) — el despertador no lanzará hasta limpiarlo"
        if [ "${1:-}" = "--fix" ]; then
            rm -rf /tmp/fondo-wake.lock
            echo "  ✅ lock huérfano LIMPIADO (--fix)"
        else
            echo "  → ejecuta con --fix para limpiarlo: bash ura-fondo-health.sh --fix"
        fi
    fi
else
    echo "  OK — sin lock (despertador libre)"
fi

echo "=== 4. Último run de fondo ==="
grep "run de fondo terminado" "$LOG" 2>/dev/null | tail -1 || echo "  ⚠️ sin runs registrados"
grep "carpeta a revisar" "$LOG" 2>/dev/null | tail -1 || true

echo "=== 5. Progreso (carpetas revisadas) ==="
grep -A40 "## Progreso" "$FONDO_FILE" 2>/dev/null | grep '^| 2026' | grep -oE '^\| [0-9-]+ \| [a-z/.]+' | tail -8 || echo "  ⚠️ sin progreso"

echo "=== 6. Hallazgos por estado ==="
if [ -f "$FONDO_FILE" ]; then
    TOTAL=$(grep -c '^| 2026' "$FONDO_FILE")
    ABIERTOS=$(grep '^| 2026' "$FONDO_FILE" | grep -cE "abierto|propuesto")
    CORREGIDOS=$(grep '^| 2026' "$FONDO_FILE" | grep -c "corregido")
    echo "  total=$TOTAL | pendientes=$ABIERTOS | corregidos=$CORREGIDOS"
else
    echo "  ⚠️ archivo de hallazgos no encontrado"
fi

echo "=== 7. Repo Mac limpio (solo hallazgos esperados)? ==="
cd "$REPO" 2>/dev/null && git status --short 2>/dev/null | grep -vE "hallazgos-fondo|mutation" | head -4 || echo "  OK/irrelevante"
