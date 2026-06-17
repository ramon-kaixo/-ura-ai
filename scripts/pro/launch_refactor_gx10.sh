#!/usr/bin/env bash
set -euo pipefail

# ══════════════════════════════════════════════════════════════════
#  TUNELADORA SCA — Handshake + Ciga-Free + Reporte de Seguimiento
# ══════════════════════════════════════════════════════════════════

cd /home/ramon/URA/ura_ia_1972
export PATH="$HOME/.local/bin:$PATH"
PYTHON="/home/ramon/URA/ura_ia_1972/.venv/bin/python3"

T0=$(date +%s)
echo "⛏️  TUNELADORA SCA — $(date "+%H:%M:%S") — Iniciando ciclo de excavacion"

# ── HANDSHAKE: Solicitar lista de limpieza al Guardian ──
echo "🤝 Handshake: solicitando sistema_map.json al Guardian..."
if [ -f .nervioso/sistema_map.json ]; then
  # Re-indexar para asegurar datos frescos
  $PYTHON scripts/openclaw_indexer.py scan 2>/dev/null || echo "⚠️  Indexer no disponible — usando cache"
  DUPLICADOS=$($PYTHON -c "
import json
d=json.load(open('.nervioso/sistema_map.json'))
dupes=sum(1 for n in d.get('dependency_graph',{}).values() if 'ESPEJO' in n.get('pipeline_state',''))
print(dupes)
" 2>/dev/null || echo 0)
  ACTIVOS=$($PYTHON -c "
import json
d=json.load(open('.nervioso/sistema_map.json'))
act=sum(1 for n in d.get('dependency_graph',{}).values() if 'ESPEJO' not in n.get('pipeline_state','') and 'ZOMBIE' not in n.get('pipeline_state',''))
print(act)
" 2>/dev/null || echo 0)
  echo "📋 Guardian: $ACTIVOS activos, $DUPLICADOS duplicados excluidos (Ciga-Free)"
else
  echo "⚠️  Sin sistema_map.json — ejecutando sin filtro de limpieza"
fi

# ── MODO PROFUNDO: Si es dia 01 o --force-all, ignorar delta-check ──
DIA_ACTUAL=$(date +%d)
FORCE_ALL="${1:-}"
if [ "$FORCE_ALL" = "--force-all" ] || [ "$DIA_ACTUAL" = "01" ]; then
  echo "⚠️  MODO PROFUNDO: dia $DIA_ACTUAL — ignorando delta-check, procesando TODO"
  # Borrar delta snapshot para forzar reprocesamiento completo
  rm -f .nervioso/delta_snapshots/ultimo_ciclo.json 2>/dev/null
  echo "🧹 Delta snapshots reseteados — todos los archivos se reprocesaran"
fi

rm -f /tmp/refactor_gx10_*.log /tmp/refactor_gx10_*.pid /tmp/refactor_watchdog.pid /tmp/refactor_watchdog.log
rm -f .refactor_blocked

echo "⛏️  Excavacion Ciga-Free: 4 workers, sin analisis de redundancia"
for i in 1 2 3 4; do
  nohup env REFACTOR_WORKER_ID=$i REFACTOR_WORKER_TOTAL=4 \
    REFACTOR_MODEL=qwen2.5-coder:14b \
    MONSTER_THRESHOLD=80 \
    MAX_BATCH_TOKENS=6500 \
    PROMPT_OVERHEAD_TOKENS=800 \
    OLLAMA_URL=http://${ASUS_HOST:-10.164.1.99}:11434 \
    URA_ROOT="$HOME/URA/ura_ia_1972" \
    PATH="$HOME/.local/bin:$PATH" \
    $PYTHON -B scripts/pro/refactor_large_functions.py \
    >> "/tmp/refactor_gx10_$i.log" 2>&1 &
  echo $! > "/tmp/refactor_gx10_$i.pid"
  echo "W$i PID=$!"
done

nohup $PYTHON scripts/pro/refactor_watchdog.py --daemon \
  >> /tmp/refactor_watchdog.log 2>&1 &
echo $! > /tmp/refactor_watchdog.pid
echo "WDOG PID=$!"

sleep 5
echo "=== ESTADO ==="
for i in 1 2 3 4; do
  pid=$(cat "/tmp/refactor_gx10_$i.pid" 2>/dev/null || echo 0)
  if kill -0 "$pid" 2>/dev/null; then
    lines=$(wc -l < "/tmp/refactor_gx10_$i.log" 2>/dev/null || echo 0)
    echo "W$i PID=$pid VIVO log=$lines lineas"
    head -3 "/tmp/refactor_gx10_$i.log"
  else
    echo "W$i PID=$pid MUERTO"
  fi
done
echo "=== Watchdog ==="
cat /tmp/refactor_watchdog.pid 2>/dev/null

# ── REPORTE DE SEGUIMIENTO (SCA) ──
echo ""
# ── REPORTE FINAL DE AUDITORIA DE TIEMPO ──
T1=$(date +%s)
TIEMPO_TOTAL=$((T1 - T0))

# Contar archivos procesados vs saltados
SALTADOS_DELTA=$(grep -c 'sin cambios' /tmp/refactor_gx10_1.log /tmp/refactor_gx10_2.log /tmp/refactor_gx10_3.log /tmp/refactor_gx10_4.log 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')
PROCESADOS_TOTAL=$(grep -c '📁' /tmp/refactor_gx10_1.log /tmp/refactor_gx10_2.log /tmp/refactor_gx10_3.log /tmp/refactor_gx10_4.log 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')
CHUNKS_OK=$(grep -c '✅ OK\|✅ Chunk' /tmp/refactor_gx10_1.log /tmp/refactor_gx10_2.log /tmp/refactor_gx10_3.log /tmp/refactor_gx10_4.log 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')
CHUNKS_ERR=$(grep -c '❌ Error\|❌ Respuesta\|⚠️ Chunk' /tmp/refactor_gx10_1.log /tmp/refactor_gx10_2.log /tmp/refactor_gx10_3.log /tmp/refactor_gx10_4.log 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')

# Formatear tiempo
H=$((TIEMPO_TOTAL / 3600))
M=$(((TIEMPO_TOTAL % 3600) / 60))
S=$((TIEMPO_TOTAL % 60))

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  📊 INFORME DE EXCAVACION — Tuneladora SCA"
echo "══════════════════════════════════════════════════════════"
echo "  ⏱️  Tiempo total:       ${H}h ${M}m ${S}s"
echo "  📁 Archivos procesados: $PROCESADOS_TOTAL"
echo "  Δ  Saltados (sin cambio): $SALTADOS_DELTA"
echo "  ✅ Chunks OK:          $CHUNKS_OK"
echo "  ❌ Chunks error:       $CHUNKS_ERR"
if [ $PROCESADOS_TOTAL -gt 0 ]; then
  PROMEDIO=$((TIEMPO_TOTAL / PROCESADOS_TOTAL))
  echo "  ⏱️  Promedio/archivo:   ${PROMEDIO}s"
fi
echo "  🧠 Ciga-Free:          $DUPLICADOS duplicados excluidos por Guardian"
echo "══════════════════════════════════════════════════════════"
echo "⛏️  Excavacion completada — $(date "+%H:%M:%S")"

# ── DELTA SNAPSHOT: guardar estado para proximo ciclo ──
echo ""
echo "💾 Guardando delta snapshot para proximo ciclo..."
$PYTHON -c "
import sys; sys.path.insert(0,'scripts')
from openclaw_firmador import delta_snapshot
path = delta_snapshot('ultimo_ciclo')
print(f'   Delta snapshot: {path}')
" 2>/dev/null || echo "   ⚠️  Delta snapshot fallo"
echo "🌱 Siguiente ciclo: $(date -d '+6 hours' '+%H:%M' 2>/dev/null || date -v +6H '+%H:%M' 2>/dev/null || echo 'en 6h')"
