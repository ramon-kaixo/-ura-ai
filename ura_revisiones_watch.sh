#!/bin/bash
# Watchdog Mac v3.1 — cierra el circulo Mac->ASUS (fix bucle auto-merge 2026-08-10)
#
# FIX (TASK-20260810-004): el merge incondicional 'git merge asus/main --no-ff'
# creaba un commit de merge NUEVO cada 5 min aunque no hubiera cambios, lo que
# disparaba el detector de ASUS (merge de mac-veredictos -> main) y asi
# indefinidamente (bucle Mac<->ASUS, borro trabajo sin commitear el 19:05:26).
# Ahora:
#   * solo se integra asus/main si NO es ya ancestro de HEAD (nada que hacer)
#   * si HEAD es ancestro de asus/main -> fast-forward puro (sin commit nuevo)
#   * solo merge --no-ff real cuando hay divergencia genuina (ambas ramas
#     tienen commits que la otra no)
#
# 1) EMPUJA a ASUS (rama mac-veredictos) los veredictos del Escritorio
# 2) ASUS integra via detector (merge de mac-veredictos -> main)
# 3) Consulta ASUS por pendientes y notifica en el Mac.
set -u
MAC_REPO="$HOME/URA/ura_ia_1972"
cd "$MAC_REPO" || exit 1

# --- 1) Integrar main de ASUS SOLO si hay novedades (anti-bucle) ---
git fetch asus main 2>/dev/null
if ! git merge-base --is-ancestor asus/main HEAD 2>/dev/null; then
    if git merge-base --is-ancestor HEAD asus/main 2>/dev/null; then
        # Solo retrasados: fast-forward sin crear commit de merge
        git merge asus/main --ff-only 2>/dev/null
        echo "INTEGRATE_FF: main de ASUS adelantado (sin merge commit)"
    else
        # Divergencia real (Mac y ASUS tienen commits propios)
        git merge asus/main --no-ff -m "merge: base Mac con ASUS" 2>/dev/null
        echo "INTEGRATE_MERGE: divergencia real integrada"
    fi
else
    echo "INTEGRATE_SKIP: main de ASUS ya integrado (sin novedades)"
fi

# --- 2) Commit de veredictos locales (docs/udo/) en rama DEDICADA ---
# v3.3 (TASK-20260818-011): rsync --delete sustituye a cp -r — los expedientes
# borrados en el repo principal tambien se borran en el worktree (cp no borra).
# v3.2 (TASK-20260818-008): los veredictos se commitean en un worktree de
# mac-veredictos, NO en la rama actual — evita contaminar la rama de tarea
# del TERM (divergencias Mac<->ASUS, auto-push fantasma) sin tocar el
# working tree principal.
WT="/tmp/mac-veredictos-wt"
if [ -n "$(git status -s docs/udo/ 2>/dev/null | head -1)" ]; then
    if [ ! -d "$WT/.git" ]; then
        git worktree remove --force "$WT" 2>/dev/null
        git worktree add -f "$WT" mac-veredictos 2>/dev/null || { echo "WORKTREE_FAIL"; exit 1; }
    fi
    rsync -a --delete docs/udo/ "$WT/docs/udo/" 2>/dev/null
    (cd "$WT" && git add -A docs/udo/ 2>/dev/null \
        && git commit -m "chore(udo): [TERM] veredictos revisor desde Escritorio (auto-push)" 2>/dev/null \
        && git fetch asus mac-veredictos 2>/dev/null \
        && git push asus mac-veredictos --force-with-lease 2>&1 | tail -1 \
        && echo "PUSH_VEREDICTOS_OK (worktree mac-veredictos)")
else
    echo "PUSH_SKIP: sin veredictos nuevos que empujar"
fi

# --- 4) Consultar ASUS por pendientes y notificar ---
OUT=$(ssh -o ConnectTimeout=8 -o BatchMode=yes gx10 "/home/ramon/URA/ura_ia_1972/scripts/pro/detectar_revisiones.sh" 2>/dev/null)
N=$(echo "$OUT" | grep -c "TASK-")
if [ "$N" -gt 0 ]; then
    RESUMEN=$(echo "$OUT" | grep "TASK-" | head -3 | sed "s/^[[:space:]]*//")
    if [ "$(cat ~/.ura_revisiones_last 2>/dev/null)" != "$N" ]; then
        osascript -e "display notification \"$N tarea(s) pendientes: $RESUMEN\" with title \"URA - Revisiones pendientes\"" 2>/dev/null
        echo "$N" > ~/.ura_revisiones_last
    fi
fi