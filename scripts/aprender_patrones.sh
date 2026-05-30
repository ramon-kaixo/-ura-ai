#!/bin/bash
set -euo pipefail
# aprender_patrones.sh — Calcula ocupacion por hora y dia de la semana
ANALISIS_DIR="${HOME}/URA/ura_ia_1972/knowledge/analisis_periodos"
MODELO="${HOME}/URA/ura_ia_1972/knowledge/modelo_patrones/patrones.json"
mkdir -p "$(dirname "$MODELO")"

# Versionar modelo anterior antes de sobrescribir
[ -f "$MODELO" ] && bash "${HOME}/URA/ura_ia_1972/scripts/versionar_conocimiento.sh" "$MODELO" 2>/dev/null || true

find "$ANALISIS_DIR" -name "*.json" -mtime -30 2>/dev/null | python3 -c "
import json, sys
from datetime import datetime
from collections import Counter, defaultdict

patrones_hora = Counter()
dia_semana = Counter()
total_eventos = 0

for f in sys.stdin:
    f = f.strip()
    try:
        with open(f) as fp:
            datos = json.load(fp)
        for evento in datos:
            ini = evento.get('inicio', '')
            if ini:
                dt = datetime.fromisoformat(ini)
                clave = f\"{dt.strftime('%A')}-{dt.hour}h\"
                patrones_hora[clave] += 1
                dia_semana[dt.strftime('%A')] += 1
                total_eventos += 1
    except:
        pass

modelo = {
    'ocupacion_por_hora': dict(patrones_hora.most_common(50)),
    'dia_semana': dict(dia_semana.most_common(7)),
    'total_eventos': total_eventos,
    'ultima_actualizacion': datetime.now().isoformat()
}

with open('$MODELO', 'w') as f:
    json.dump(modelo, f, indent=2)

print(f'OK {total_eventos} eventos, {len(patrones_hora)} franjas')
" 2>/dev/null || echo "Sin datos para patrones"

# Rotacion de analisis antiguos (>90 dias)
find "$ANALISIS_DIR" -name "*.json" -mtime +90 -delete 2>/dev/null || true
echo "🧹 Analisis antiguos eliminados"
