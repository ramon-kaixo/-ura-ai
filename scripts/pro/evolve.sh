#!/bin/bash
set -euo pipefail
# Evolve — Analiza tendencias y sugiere ajustes automáticos
echo "🧬 Análisis evolutivo — $(date)"
METRICS_DIR="${HOME}/URA/ura_ia_1972/docs/metrics"

python3 << PYEOF
import json, os, glob
from datetime import datetime, timedelta

metrics_dir = os.path.expanduser("$METRICS_DIR")
files = sorted(glob.glob(f"{metrics_dir}/quality_*.json"))

if len(files) < 2:
    print("⚠️  Necesitas al menos 2 métricas para comparar tendencias")
    exit(0)

# Cargar última y anterior
with open(files[-1]) as f: last = json.load(f)
with open(files[-2]) as f: prev = json.load(f)

print(f"📊 Comparando: {os.path.basename(files[-2])} → {os.path.basename(files[-1])}")
print()

cambios = []
for key in ["lineas", "tests_pasados", "archivos_grandes"]:
    diff = last.get(key, 0) - prev.get(key, 0)
    if diff > 0:
        cambios.append(f"  {key}: +{diff} ↑")
    elif diff < 0:
        cambios.append(f"  {key}: {diff} ↓")
    else:
        cambios.append(f"  {key}: = (sin cambios)")

for c in cambios:
    print(c)

print()
# Detectar tendencias
if last.get("archivos_grandes", 0) > prev.get("archivos_grandes", 0):
    print("⚠️  Tendencia: aumentan archivos >200 líneas. Sugerir refactor.")
if last.get("tests_pasados", 0) < prev.get("tests_pasados", 0):
    print("🔴 Tendencia: menos tests pasando. Revisar cambios recientes.")
if last.get("complejidad_media", "?") != "?" and prev.get("complejidad_media", "?") != "?":
    print(f"📐 Complejidad: {prev.get('complejidad_media')} → {last.get('complejidad_media')}")
PYEOF

echo "✅ Análisis evolutivo completado"
