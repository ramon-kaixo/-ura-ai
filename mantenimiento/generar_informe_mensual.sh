#!/bin/bash
REPO_DIR="/home/ramon/URA/ura_ia_1972"
cd "$REPO_DIR"

python3 mantenimiento/detectar_patrones.py 2>/dev/null

if [ -f /tmp/informe_patrones_mensual.json ]; then
    python3 -c "
import json
d = json.load(open('/tmp/informe_patrones_mensual.json'))
print('# VALORACION DE DANOS — URA v3.1')
print(f'Periodo: mes actual')
print(f'Fallos totales: {d[\"total_fallos\"]}')
print(f'Patrones detectados: {len(d[\"patrones\"])}')
for p in d['patrones']:
    print(f'  - {p[\"error\"]}: {p[\"repeticiones\"]} veces (ultimo: {p[\"ultimo\"][:10]})')
" > "$REPO_DIR/mantenimiento/informe_mensual.md"
    python3 /home/ramon/URA/ura_ia_1972/core/utils/anonymizer.py "$REPO_DIR/mantenimiento/informe_mensual.md"
    $old
    echo "[✓] Informe mensual generado y enviado al Mac."
else
    echo "[i] Sin fallos registrados este mes. Informe limpio."
    echo "# VALORACION DE DANOS — URA v3.1" > "$REPO_DIR/mantenimiento/informe_mensual.md"
    echo "Periodo: mes actual — Sin fallos registrados." >> "$REPO_DIR/mantenimiento/informe_mensual.md"
fi
