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

# Carpeta pendiente: primera del mapa no aparecida en la sección Progreso
CANDIDATA=""
REVISADAS=$(grep -oE '^\| [0-9-]{10} \| [^|]+ \|' "$FONDO_FILE" 2>/dev/null | awk -F'|' '{print $3}' | sed 's/^ *//;s/ *$//')
for c in "${MAPA_CARPETAS[@]}"; do
    if ! grep -qF "$c" <<< "$REVISADAS" 2>/dev/null; then
        CANDIDATA="$c"
        break
    fi
done

if [ -z "$CANDIDATA" ]; then
    echo "[$(date +%H:%M:%S)] mapa de carpetas agotado — revisando de nuevo desde el inicio (ciclo 2)" >> "$LOG"
    CANDIDATA="${MAPA_CARPETAS[0]}"
fi
echo "[$(date +%H:%M:%S)] sesión: $SES | carpeta a revisar: $CANDIDATA" >> "$LOG"

MSG="MODO FONDO (v1.10): no es una tarea nueva del humano. Entra en modo de revision autonoma de fondo. TU CARPETA PARA ESTE TURNO ES EXACTAMENTE: '$CANDIDATA'. Revisa esa carpeta (lee sus archivos con read/grep/glob/ls, recorre subcarpetas). Busca fallos, duplicados, codigo muerto, contradicciones, deuda tecnica. Registra en docs/udo/hallazgos-fondo.md cada hallazgo con estado 'propuesto (con plan)' (QUE/POR QUE/IMPACTO/VERIFICACION/RIESGO) y añade '$CANDIDATA' a la seccion ## Progreso (fecha + carpeta + resultado). PROHIBIDO ESCRITURA: write/edit/patch estan deshabilitadas; usa solo lectura. Si la carpeta no existe o no tienes permisos, registralo en Progreso como revisada y termina. Luego termina el turno."

cd "$REPO" || exit 1
"$OC" run --attach "$URL" -s "$SES" --fork --agent revisor-fondo --format json "$MSG" >> "$LOG" 2>&1
RUN_EXIT=$?

echo "[$(date +%H:%M:%S)] run de fondo terminado (exit=$RUN_EXIT)" >> "$LOG"

# Si el run terminó OK pero el TERM no registró la carpeta en Progreso
# (p.ej. carpeta de shims sin hallazgos), el despertador la marca como
# revisada para que el mapa avance en el siguiente ciclo.
if [ "$RUN_EXIT" -eq 0 ] && ! grep -qF "$CANDIDATA" <<< "$(grep -A20 '## Progreso' "$FONDO_FILE" 2>/dev/null || true)"; then
    FECHA=$(date +%Y-%m-%d)
    printf '| %s | %s | Revisada por modo fondo (registro automático del despertador, sin hallazgos accionables). |\n' "$FECHA" "$CANDIDATA" >> "$FONDO_FILE"
    echo "[$(date +%H:%M:%S)] progreso registrado automáticamente: $CANDIDATA" >> "$LOG"
fi

exit 0
