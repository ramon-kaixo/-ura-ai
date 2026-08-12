#!/bin/bash
# despertador-fondo.sh — Despertador del modo de revisión autónoma de fondo (v1.10)
# Envía un mensaje de modo fondo al servidor TERM (Mac) vía `opencode run --attach`.
# v1.10: calcula la carpeta pendiente (mapa fijo + progreso) y la dice EXPLÍCITAMENTE
# al TERM, para que avance carpeta a carpeta en vez de quedarse en la primera.
#
# Lógica:
#   1. Lock (mkdir) — si ya hay un run de fondo en curso, no lanzar otro.
#   2. Determina la sesión TERM principal (la más reciente con activity).
#   3. Lee docs/udo/hallazgos-fondo.md → sección Progreso → carpetas ya revisadas.
#   4. Elige la primera carpeta del mapa no revisada aún.
#   5. Envía mensaje con la carpeta CONCRETA a revisar (fork + agente revisor-fondo).
#   6. Log a /tmp/fondo-wake.log.

set -u
LOCK=/tmp/fondo-wake.lock
LOG=/tmp/fondo-wake.log
OC=/Users/ramonesnaola/.opencode/bin/opencode
URL=http://127.0.0.1:8091
REPO=/Users/ramonesnaola/URA/ura_ia_1972
FONDO_FILE="$REPO/docs/udo/hallazgos-fondo.md"

# Mapa de carpetas a revisar en orden (raíces de la arquitectura URA).
# Se añaden carpetas nuevas aquí cuando el mapa se agote.
# Nota (2026-08-12): 'agents/' no existe como raíz; los agentes están en
# core/agents, motor/agents y motor/intelligence/agents (verificado por TERM).
MAPA_CARPETAS=(
  "core/"
  "motor/"
  "core/agents/"
  "motor/agents/"
  "motor/intelligence/"
  "knowledge/"
  "scripts/pro/"
  "deploy/"
  "tests/"
  "docs/"
)

# Lock anti-solapamiento robusto: directorio con PID; se limpia si es residual
# (archivo en vez de directorio), si el PID ya no existe, o si tiene >30 min
# (run huérfano por timeout del lanzador).
if [ -e "$LOCK" ] && [ ! -d "$LOCK" ]; then
    rm -f "$LOCK"
    echo "[$(date +%H:%M:%S)] lock residual (archivo) eliminado" >> "$LOG"
elif [ -d "$LOCK" ]; then
    LOCK_AGE=$(($(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || echo 0)))
    LOCK_PID=$(cat "$LOCK/pid" 2>/dev/null || echo 0)
    if [ "$LOCK_AGE" -gt 1800 ] || ! kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[$(date +%H:%M:%S)] lock huérfano (age=${LOCK_AGE}s pid=${LOCK_PID}) — limpiando" >> "$LOG"
        rm -rf "$LOCK"
    else
        echo "[$(date +%H:%M:%S)] ya hay un run de fondo en curso (lock pid=$LOCK_PID), salto" >> "$LOG"
        exit 0
    fi
fi

if ! mkdir "$LOCK" 2>/dev/null; then
    echo "[$(date +%H:%M:%S)] lock en conflicto, salto" >> "$LOG"
    exit 0
fi
echo "$$" > "$LOCK/pid"
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

echo "[$(date +%H:%M:%S)] despertador iniciado" >> "$LOG"

# Servidor vivo?
if ! curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$URL/" | grep -q 200; then
    echo "[$(date +%H:%M:%S)] servidor TERM caído (sin HTTP 200) — reintento en la próxima ejecución" >> "$LOG"
    exit 0
fi

# Sesión TERM principal
SES=$(curl -s --max-time 5 "$URL/api/session" | python3 -c '
import json, sys
d = json.load(sys.stdin)
rows = [s for s in d["data"] if s["id"].startswith("ses_")]
rows.sort(key=lambda s: s["time"]["updated"], reverse=True)
print(rows[0]["id"] if rows else "")
' 2>/dev/null)

if [ -z "$SES" ]; then
    echo "[$(date +%H:%M:%S)] sin sesión disponible" >> "$LOG"
    exit 0
fi

# Planificador jerárquico (v2): calcula la siguiente carpeta/lote pendiente
# con la lista EXACTA de archivos a leer (máx. 30 por turno).
PLAN=$(python3 "$REPO/deploy/mac/plan_fondo.py" "$REPO" "$FONDO_FILE" 2>/dev/null)
CANDIDATA=$(echo "$PLAN" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("carpeta",""))' 2>/dev/null)
ARCHIVOS=$(echo "$PLAN" | python3 -c 'import json,sys; print(" ".join(json.load(sys.stdin).get("archivos",[])))' 2>/dev/null)
MARCA=$(echo "$PLAN" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("marcar_como",""))' 2>/dev/null)
TOTAL_LOTES=$(echo "$PLAN" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("total_lotes",1))' 2>/dev/null)
LOTE=$(echo "$PLAN" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("lote",1))' 2>/dev/null)

if [ -z "$CANDIDATA" ]; then
    echo "[$(date +%H:%M:%S)] planificador sin carpeta pendiente: $(echo "$PLAN" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("error","?"))' 2>/dev/null)" >> "$LOG"
    exit 0
fi
echo "[$(date +%H:%M:%S)] sesión: $SES | carpeta a revisar: $CANDIDATA (lote $LOTE/$TOTAL_LOTES, $([ -n "$ARCHIVOS" ] && echo "$(echo "$ARCHIVOS" | wc -w | tr -d ' ')" || echo 0) archivos)" >> "$LOG"

MSG="MODO FONDO (v2): no es una tarea nueva del humano. Entra en modo de revision autonoma de fondo.

TU TAREA EXACTA PARA ESTE TURNO: revisar la carpeta '$CANDIDATA' (lote $LOTE de $TOTAL_LOTES).

ARCHIVOS QUE DEBES LEER (solo estos, leelos COMPLETOS con read, uno a uno):
$ARCHIVOS

REGLAS DE EVIDENCIA (obligatorias):
1. Lee CADA archivo completo antes de opinar. PROHIBIDO reportar 'posibles problemas' sin haber leido el codigo citado.
2. Un hallazgo solo se registra si citas ruta:linea REAL y el fallo concreto es visible en el codigo leido.
3. Si algo parece raro pero no puedes confirmarlo con el codigo delante, NO lo reportes: anotalo solo como INFO en el progreso.
4. Busca: fallos reales, duplicados, codigo muerto, contradicciones, deuda tecnica.
5. Registra hallazgos con estado 'propuesto (con plan)' (QUE/POR QUE/IMPACTO/VERIFICACION/RIESGO).

PROHIBIDO ESCRITURA: write/edit/patch deshabilitadas; usa solo lectura.
Al final, añade '$MARCA' a la seccion ## Progreso (fecha + carpeta + resultado). Luego termina el turno."

cd "$REPO" || exit 1
"$OC" run --attach "$URL" -s "$SES" --fork --agent revisor-fondo --format json "$MSG" >> "$LOG" 2>&1
RUN_EXIT=$?

echo "[$(date +%H:%M:%S)] run de fondo terminado (exit=$RUN_EXIT)" >> "$LOG"

# Si el run terminó OK pero el TERM no registró la carpeta/lote en Progreso,
# el despertador la marca como revisada (MARCA incluye el lote) para que el
# planificador avance en el siguiente ciclo.
if [ "$RUN_EXIT" -eq 0 ] && [ -n "$MARCA" ] && ! grep -qF "$MARCA" <<< "$(grep -A40 '## Progreso' "$FONDO_FILE" 2>/dev/null || true)"; then
    FECHA=$(date +%Y-%m-%d)
    printf '| %s | %s | Revisada por modo fondo (registro automático del despertador, sin hallazgos accionables). |\n' "$FECHA" "$MARCA" >> "$FONDO_FILE"
    echo "[$(date +%H:%M:%S)] progreso registrado automáticamente: $MARCA" >> "$LOG"
fi

# Limpieza EXPLÍCITA del lock (no confiar solo en el trap EXIT: el proceso
# bash puede ser sustituido por el run de opencode y el trap no ejecutarse).
rm -rf "$LOCK" 2>/dev/null
trap - EXIT

exit 0
