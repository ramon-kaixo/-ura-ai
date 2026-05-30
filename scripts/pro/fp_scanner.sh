#!/bin/bash
set -euo pipefail
# FP Scanner — Identifica falsos positivos conocidos en reportes de herramientas
echo "📊 FP Scanner — Analizando falsos positivos conocidos..."
REPORT_DIR="${HOME}/URA/ura_ia_1972/docs/pro/reports"
mkdir -p "$REPORT_DIR"
FP_LOG="${REPORT_DIR}/fp_log.txt"

# Lista de falsos positivos CONOCIDOS (por archivo y patrón)
KNOWN_FP=(
    "B104:0.0.0.0:Intencional para servidores de desarrollo"
    "B324:md5:Intencional para generación de cachés"
    "B108:/tmp:Intencional en scripts de prueba"
    "B310:urlopen:Intencional para healthchecks locales"
)

echo "=== Falsos positivos conocidos ===" | tee "$FP_LOG"
for fp in "${KNOWN_FP[@]}"; do
    IFS=':' read -r code pattern reason <<< "$fp"
    echo "   🟢 $code ($pattern): $reason" | tee -a "$FP_LOG"
done

echo "" | tee -a "$FP_LOG"
echo "=== Último reporte de wraith (si existe) ===" | tee -a "$FP_LOG"
ls -t "${REPORT_DIR}"/*wraith*.json 2>/dev/null | head -1 | while read f; do
    python3 -c "
import json
with open('$f') as fp:
    d = json.load(fp)
issues = d.get('issues', d.get('results', []))
print(f'   Total hallazgos: {len(issues)}')
print(f'   Documentados como FP: 0 (pendiente de revisión manual)')
" 2>/dev/null || echo "   (no se pudo analizar)"
done

echo "✅ FP Scanner completado — log en $FP_LOG"
