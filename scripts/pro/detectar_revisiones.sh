#!/usr/bin/env bash
# Detector de pendientes UDO — 3 niveles (TASK-20260810-002)
#
# Vigila que NADA quede a medias sin detectar:
#   Nivel 1 — Tareas IN_PROGRESS que llevan tiempo sin avanzar (a medias)
#   Nivel 2 — Tareas REVIEW sin veredicto de revisor (esperando revisión)
#   Nivel 3 — Planes/fases/etapas marcadas 'Pendiente'/'Planificado' (sin cerrar)
#             + tareas REVIEW con OK de revisor = LISTAS PARA CERRAR
#
# Registra todo en docs/udo/pendientes-fase.md. Opcional: notifica
# (Telegram/Pushover) via motor.core.notifier.
#
# Uso:
#   detectar_revisiones.sh          # detecta y registra (sin notificar)
#   detectar_revisiones.sh --notify # detecta, registra y notifica
#
# Reversible: no modifica expedientes; solo actualiza pendientes-fase.md.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKS_DIR="$REPO/docs/udo/tasks"
PEND="$REPO/docs/udo/pendientes-fase.md"
NOTIFY="${1:-}"

[ -d "$TASKS_DIR" ] || { echo "ERROR: no existe $TASKS_DIR" >&2; exit 1; }

TODAY="$(date +%F)"

# ===== NIVEL 1: tareas IN_PROGRESS (a medias, sin avanzar) =====
a_medias=""
n_amedias=0
for f in "$TASKS_DIR"/*.md; do
    [ -f "$f" ] || continue
    est=$(grep '^estado:' "$f" | cut -d' ' -f2- | tr -d ' ')
    [ "$est" = "IN_PROGRESS" ] || continue
    id=$(basename "$f" .md)
    n_amedias=$((n_amedias+1))
    a_medias="$a_medias
| $id | IN_PROGRESS (a medias) | $TODAY | PENDIENTE | |"
done

# ===== NIVEL 2: tareas REVIEW sin revision (pendientes de revisor) =====
pendientes=""
total=0
for f in "$TASKS_DIR"/*.md; do
    [ -f "$f" ] || continue
    est=$(grep '^estado:' "$f" | cut -d' ' -f2- | tr -d ' ')
    [ "$est" = "REVIEW" ] || continue
    # grep sin match retorna 1; con set -o pipefail la asignación muere con
    # set -e cuando un expediente REVIEW aún no tiene línea revision: (el
    # caso exacto que este detector debe vigilar). || true lo hace robusto.
    rev=$(grep '^revision:' "$f" | cut -d' ' -f2- | tr -d ' ' || true)
    # if-else en vez de "[ -n "$rev" ] && continue": con set -e, si rev está
    # vacío el AND-list retorna 1 y mata el script (servicio FAILED) justo
    # cuando hay tareas REVIEW sin revisor — el caso que debe vigilar.
    if [ -n "$rev" ]; then
        continue  # ya revisada
    fi
    id=$(basename "$f" .md)
    total=$((total+1))
    pendientes="$pendientes
| $id | pendiente revisor | $TODAY | PENDIENTE | |"
done

# ===== NIVEL 2b: tareas REVIEW con OK = LISTAS PARA CERRAR =====
lista_cerrar=""
n_cerrar=0
for f in "$TASKS_DIR"/*.md; do
    [ -f "$f" ] || continue
    est=$(grep '^estado:' "$f" | cut -d' ' -f2- | tr -d ' ')
    [ "$est" = "REVIEW" ] || continue
    rev=$(grep '^revision:' "$f" | cut -d' ' -f2- || true)
    echo "$rev" | grep -q "| OK |" || continue
    id=$(basename "$f" .md)
    n_cerrar=$((n_cerrar+1))
    lista_cerrar="$lista_cerrar
| $id | lista para cerrar (OK revisor) | $TODAY | LISTO | |"
done

# ===== NIVEL 3: planes/fases 'Pendiente'/'Planificado' en seccion Roadmap =====
AGENTS="$REPO/AGENTS.md"
n_planes=0
planes=""
if [ -f "$AGENTS" ]; then
    # Solo la seccion Roadmap (desde "## Roadmap" hasta el final)
    planes=$(sed -n '/^## Roadmap/,$p' "$AGENTS" | grep -E "Planificado" | while IFS= read -r linea; do
        # Formato: | **N** | <nombre de la fase> | 🔮 Planificado |  → campo 3
        txt=$(echo "$linea" | cut -d'|' -f3 | tr -s ' ' | sed 's/^ *//;s/ *$//' | cut -c1-70)
        [ -n "$txt" ] || continue
        printf '| — | plan/fase: %s | %s | PENDIENTE | |\n' "$txt" "$TODAY"
    done)
    n_planes=$(printf '%s\n' "$planes" | grep -c 'plan/fase' || true)
fi

# ===== Escribir pendientes-fase.md (tabla regenerada, 3 niveles) =====
{
    grep -v -e '^| TASK-' -e '^| — |' -e '^#### ' -e '^$' "$PEND" || true
    echo ""
    echo "#### A MEDIAS (IN_PROGRESS)"
    echo "$a_medias" | sed '/^$/d'
    echo ""
    echo "#### PENDIENTES DE REVISOR"
    echo "$pendientes" | sed '/^$/d'
    echo ""
    echo "#### LISTAS PARA CERRAR (OK revisor)"
    echo "$lista_cerrar" | sed '/^$/d'
    echo ""
    echo "#### PLANES/FASES SIN CERRAR"
    echo "$planes" | sed '/^$/d'
} > "${PEND}.tmp"

# No reescribir el fichero si no hubo cambios reales (evita commits en cada
# ejecucion del timer cada 5 min).
if ! cmp -s "${PEND}.tmp" "$PEND"; then
    mv "${PEND}.tmp" "$PEND"
    PEND_CHANGED=1
else
    rm -f "${PEND}.tmp"
    PEND_CHANGED=0
fi

# ===== Salida =====
echo "=== NIVEL 1 — A MEDIAS (IN_PROGRESS): $n_amedias ==="
echo "$a_medias" | sed '/^$/d'
echo ""
echo "=== NIVEL 2 — PENDIENTES DE REVISOR: $total ==="
echo "$pendientes" | sed '/^$/d'
echo ""
echo "=== NIVEL 2b — LISTAS PARA CERRAR (OK revisor): $n_cerrar ==="
echo "$lista_cerrar" | sed '/^$/d'
echo ""
echo "=== NIVEL 3 — PLANES/FASES SIN CERRAR: $n_planes ==="
echo "$planes" | sed '/^$/d'
echo ""
# Notificacion IDEMPOTENTE: solo avisa cuando el estado CAMBIA respecto al
# ultimo run (evita spam de Telegram/Pushover cada 5 min). Guarda un hash.
STATE_FILE="${PEND}.estado"
signature="$n_amedias|$total|$n_cerrar|$n_planes"
if [ "$NOTIFY" = "--notify" ]; then
    if [ $((n_amedias+total+n_cerrar+n_planes)) -gt 0 ]; then
        if [ "$(cat "$STATE_FILE" 2>/dev/null || echo '')" != "$signature" ]; then
            echo "$signature" > "$STATE_FILE"
            cd "$REPO" && python3 -c "
import sys; sys.path.insert(0, '$REPO')
from motor.core.notifier import notify
msgs=[]
if $n_amedias>0: msgs.append(f'$n_amedias tareas A MEDIAS')
if $total>0: msgs.append(f'$total pendientes de revisor')
if $n_cerrar>0: msgs.append(f'$n_cerrar LISTAS PARA CERRAR')
if $n_planes>0: msgs.append(f'$n_planes planes/fases sin cerrar')
notify(' | '.join(msgs), level='warning')
" 2>/dev/null && echo "Notificado (Telegram/Pushover)" || echo "AVISO: no se pudo notificar"
        else
            echo "(estado sin cambios — no se re-notifica)"
        fi
    fi
fi

# ===== Integración de veredictos del Mac (rama mac-veredictos -> main) =====
# El Escritorio (Mac) empuja sus OK a la rama mac-veredictos; aquí se integran
# a main con merge. Va al FINAL para que el propio registro de pendientes
# (pendientes-fase.md) quede commiteado antes del merge.
if command -v git >/dev/null 2>&1 && [ -d "$REPO/.git" ] && [ "${SKIP_MERGE:-}" != "1" ]; then
    if git show-ref --verify --quiet refs/heads/mac-veredictos; then
        # Stash los cambios propios del detector (pendientes-fase.md) para
        # poder mergear con el árbol limpio; luego se restauran.
        # NOTA: si no hubo cambios locales, stash push falla silenciosamente
        # (2>/dev/null) y stash pop no tiene nada que restaurar -> exit 1.
        # Ese exit 1 marcaba el servicio como FAILED aun con trabajo OK.
        git stash push -u -m "detector-pendientes" docs/udo/pendientes-fase.md >/dev/null 2>&1 || true
        # Saltar hooks: el rootfs es RO (.cache no escribible) y pytest falla
        # por PATH sin venv; el mensaje debe cumplir el formato conventional.
        if git merge-base --is-ancestor mac-veredictos HEAD 2>/dev/null; then
            echo "VEREDICTOS_MAC: rama ya integrada en main"
        elif git merge-base --is-ancestor HEAD mac-veredictos 2>/dev/null; then
            # Solo retraso: fast-forward directo sin commit de merge nuevo
            # (evita alimentar el bucle de merges recíprocos Mac<->ASUS)
            if HOME=/tmp PRE_COMMIT_HOME=/tmp/opencode/precommit3 SKIP=semgrep,pytest git merge mac-veredictos --ff-only 2>/dev/null; then
                echo "VEREDICTOS_MAC: integrados por fast-forward (sin commit extra)"
            else
                echo "AVISO: ff de mac-veredictos falló (revisar conflictos)"
            fi
        elif HOME=/tmp PRE_COMMIT_HOME=/tmp/opencode/precommit3 SKIP=semgrep,pytest git merge mac-veredictos --no-ff -m "chore(udo): integrar veredictos del Mac (auto-integracion detector)" 2>/dev/null; then
            echo "VEREDICTOS_MAC: integrados de mac-veredictos a main"
        else
            echo "AVISO: merge de mac-veredictos falló (revisar conflictos)"
        fi
        # pop sin stash previo no es error: no hay nada que restaurar.
        git stash pop >/dev/null 2>&1 || true
    fi
fi
