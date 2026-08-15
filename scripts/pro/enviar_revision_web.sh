#!/bin/bash
# enviar_revision_web.sh — Despertador de REVISION para OpenCode Web (ASUS)
# =========================================================================
# Objetivo (peticion RAMON 2026-08-13): cuando hay trabajo de revision
# pendiente, SE LE MANDA DIRECTAMENTE al OpenCode Web (sesion nueva visible en
# su panel), sin que nadie tenga que ir a buscarlo.
#
# Detectores (si CUALQUIERA tiene contenido, se envia):
#   1. docs/udo/review-pending.md  -> filas con estado 'PENDIENTE'
#   2. docs/udo/hallazgos-fondo.md -> entradas con estado 'propuesto'/'pendiente'
#   3. ura-udo list REVIEW          -> tareas UDO en espera de revisor
#
# Mecanismo de envio: `opencode run` headless en ASUS (mismo storage que el
# web server :8081) -> crea sesion nueva 'REVISION: ...' visible en el panel
# del Web con la encomienda y las rutas. No toca la sesion activa del usuario.
#
# Anti-repeticion (problema reportado por RAMON: el TERM repetia el mismo
# analisis): el script solo envia cuando el CONTENIDO pendiente cambia
# (hash del resumen pendiente vs ultimo hash enviado en /tmp/envio-web.sig).
#
# Seguridad: solo lectura; no ejecuta correcciones. Lock anti-solapamiento.
set -u
TRACE=/tmp/envio-web.trace
exec 2>>"$TRACE"
echo "[$(date '+%H:%M:%S')] TRACE inicio" >> "$TRACE"
set -x
LOCK=/tmp/envio-web.lock
LOG=/tmp/envio-web.log
SIG=/tmp/envio-web.sig
OC=/home/ramon/.opencode/bin/opencode
REPO=/home/ramon/URA/ura_ia_1972
WEB_TITLE_PREFIX="REVISION: "

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

log "inicio corrida (${USER:-unknown}, pid $$)"

# Lock anti-solapamiento (mkdir atomico; si es residual, limpiar)
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -mmin +10 2>/dev/null)" ]; then rm -rf "$LOCK"; else exit 0; fi
  if ! mkdir "$LOCK" 2>/dev/null; then exit 0; fi
fi
trap 'rm -rf "$LOCK"' EXIT

# --- 1. Detectar pendientes -------------------------------------------------
PENDIENTES=""
count=0

# 1a. review-pending.md: filas de tabla con 'PENDIENTE' en estado de revision
if [ -f "$REPO/docs/udo/review-pending.md" ]; then
  while IFS='|' read -r task _desc _commit _files _val _revisor; do
    if echo "$_val" | grep -q "PENDIENTE"; then
      count=$((count+1))
      PENDIENTES="$PENDIENTES
- $task (review-pending.md, sin veredicto)"
    fi
  done < <(grep '^| TASK-' "$REPO/docs/udo/review-pending.md")
fi

# 1b. hallazgos-fondo.md: estado propuesto/pendiente
if [ -f "$REPO/docs/udo/hallazgos-fondo.md" ]; then
  while IFS='|' read -r _f ruta hallazgo _grav estado; do
    if echo "$estado" | grep -qE "propuesto|pendiente"; then
      count=$((count+1))
      PENDIENTES="$PENDIENTES
- $ruta (hallazgos-fondo.md, estado: $estado)"
    fi
  done < <(grep '^| 2026-' "$REPO/docs/udo/hallazgos-fondo.md")
fi

# 1c. tareas UDO en REVIEW
REVIEW_TASKS=$("$REPO/scripts/pro/ura-udo" list REVIEW 2>/dev/null | grep '^TASK-' || true)
if [ -n "$REVIEW_TASKS" ]; then
  count=$((count+$(echo "$REVIEW_TASKS" | grep -c TASK)))
  PENDIENTES="$PENDIENTES
$REVIEW_TASKS"
fi

# --- 2. Si no hay pendientes: silencio (cero ruido) -------------------------
if [ "$count" -eq 0 ]; then
  log "sin pendientes — nada que enviar"
  exit 0
fi

# --- 3. Anti-repeticion: enviar solo si el contenido cambio ------------------
HASH=$(echo "$PENDIENTES" | md5sum | cut -d' ' -f1)
if [ -f "$SIG" ] && [ "$(cat "$SIG")" = "$HASH" ]; then
  log "pendientes sin cambios ($count) — no reenvio (hash $HASH)"
  exit 0
fi

# --- 4. Enviar al Web (sesion nueva visible en su panel) ----------------------
MESSAGE="ENCOMIENDA AUTOMATICA DE REVISION ($(date '+%Y-%m-%d %H:%M')): hay $count pendiente(s) de revision. Revisa y da veredicto (APROBADO / CORREGIR / DESCARTADO) para cada uno, SIN ejecutar correcciones. Detalle:$PENDIENTES

Regla: no repitas analisis ya hechos; si el pendiente no requiere accion, marca DESCARTADO con una linea."

TITLE="${WEB_TITLE_PREFIX}$count pendientes $(date '+%m-%d %H:%M')"

if timeout 300 "$OC" run --title "$TITLE" --message "$MESSAGE" >> "$LOG" 2>&1; then
  echo "$HASH" > "$SIG"
  log "ENVIADO al Web: $count pendiente(s) — sesion '$TITLE'"
else
  log "ERROR envio (codigo $?): pendientes seguiran pendientes"
fi
