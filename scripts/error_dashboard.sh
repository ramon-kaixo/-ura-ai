#!/bin/bash
set -euo pipefail
# error_dashboard.sh — Historico y tendencias de errores del Enjambre
ERROR_DIR="${HOME}/URA/ura_ia_1972/docs/errores"
INFORMES_DIR="${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/informes"
TIMESTAMP=$(date +%Y%m%d)
ERROR_FILE="${ERROR_DIR}/errores_${TIMESTAMP}.json"
mkdir -p "$ERROR_DIR"

echo "📊 Dashboard de errores — $(date)"
echo "═══════════════════════════════════"

ERRORES="["
for informe in "$INFORMES_DIR"/hallazgos_*.json; do
    [ -f "$informe" ] || continue
    buzo=$(basename "$informe" | sed 's/hallazgos_//' | sed 's/_.*//')
    count=$(jq 'length' "$informe" 2>/dev/null || echo 0)
    [ "$count" -eq 0 ] && ERRORES+="{\"buzo\":\"$buzo\",\"tipo\":\"vacio\",\"fecha\":\"$TIMESTAMP\"},"
done
ERRORES="${ERRORES%,}]"
echo "$ERRORES" > "$ERROR_FILE"

echo "   📈 Tendencias (ultimas 4 semanas):"
find "$ERROR_DIR" -name "errores_*.json" -mtime -28 -print 2>/dev/null | sort | while read f; do
    semana=$(basename "$f" .json | sed 's/errores_//')
    echo "      $semana: $(jq 'length' "$f" 2>/dev/null || echo 0) errores"
done

echo "   🏆 Top 3 buzos con mas fallos:"
jq -r '.[] | .buzo' "$ERROR_DIR"/errores_*.json 2>/dev/null | sort | uniq -c | sort -rn | head -3 || echo "      (sin datos)"

echo ""
echo "   📋 Errores por buzo (ultimos 7 dias):"
for log in /tmp/ura_errors_*.log; do
    [ -f "$log" ] || continue
    buzo_name=$(basename "$log" .log | sed 's/ura_errors_//')
    errs=$(wc -l < "$log" 2>/dev/null || echo 0)
    [ "$errs" -gt 0 ] && echo "      🔴 $buzo_name: $errs lineas"
done

echo "═══════════════════════════════════"
echo "✅ Dashboard actualizado"
