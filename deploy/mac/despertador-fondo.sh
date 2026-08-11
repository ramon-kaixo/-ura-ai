#!/bin/bash
# despertador-fondo.sh — Despertador del modo de revisión autónoma de fondo (v1.8)
# Envía un mensaje de modo fondo al servidor TERM (Mac) vía `opencode run --attach`.
# Instalación: launchd com.ura.fondo-wake (Mac) — ver deploy/mac/com.ura.fondo-wake.plist
#
# Lógica:
#   1. flock: si ya hay un run de fondo en curso, no lanzar otro.
#   2. Determina la sesión TERM principal (la más reciente con activity).
#   3. Envía el mensaje de modo fondo (read-only, 1 carpeta por turno).
#   4. Log a /tmp/fondo-wake.log.

set -u
LOCK=/tmp/fondo-wake.lock
LOG=/tmp/fondo-wake.log
OC=/Users/ramonesnaola/.opencode/bin/opencode
URL=http://127.0.0.1:8091
REPO=/Users/ramonesnaola/URA/ura_ia_1972
MAX_MIN=20

exec 9>"$LOCK"
flock -n 9 || { echo "[$(date +%H:%M:%S)] ya hay un run de fondo en curso (flock), salto" >> "$LOG"; exit 0; }

echo "[$(date +%H:%M:%S)] despertador iniciado" >> "$LOG"

# Servidor vivo?
if ! curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$URL/" | grep -q 200; then
    echo "[$(date +%H:%M:%S)] servidor TERM caído (sin HTTP 200) — reintento en la próxima ejecución" >> "$LOG"
    exit 0
fi

# Sesión TERM principal: la más reciente de la UI (excluye subagentes @general/@explore si se puede)
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
echo "[$(date +%H:%M:%S)] sesión: $SES" >> "$LOG"

MSG='MODO FONDO (v1.8): no es una tarea nueva del humano. Entra en modo de revision autonoma de fondo: revisa 1 carpeta/modulo de URA segun el progreso registrado en docs/udo/hallazgos-fondo.md (no repitas lo ya revisado). Busca fallos, duplicados, codigo muerto, contradicciones. Registra hallazgos con estado "propuesto (con plan)" (QUE/POR QUE/IMPACTO/VERIFICACION/RIESGO). PROHIBIDO ESCRITURA: no ejecutes write, edit, patch, format, ni ningun comando que modifique archivos (ni siquiera formateo/ruff); usa solo herramientas de lectura (read, grep, glob, ls) y si acaso comandos read-only. Si algo requiere correccion, registra el hallazgo con plan y termina. Registra el progreso de la carpeta revisada. Luego termina el turno.'

cd "$REPO" || exit 1
"$OC" run --attach "$URL" -s "$SES" --format json "$MSG" >> "$LOG" 2>&1

echo "[$(date +%H:%M:%S)] run de fondo terminado (exit=$?)" >> "$LOG"
exit 0
