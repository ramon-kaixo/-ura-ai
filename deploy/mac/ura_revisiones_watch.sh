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

# --- 2) Commit de veredictos locales (docs/udo/) ---
if [ -n "$(git status -s docs/udo/ 2>/dev/null | head -1)" ]; then
    git add docs/udo/
    git commit -m "chore(udo): [TERM] veredictos revisor desde Escritorio (auto-push)" 2>/dev/null
fi

# --- 3) Rama intermedia y push ---
# Actualizar lease local antes del push (force-with-lease falla si la ref
# de seguimiento esta vieja: el fetch del paso 1 solo trae main)
git fetch asus mac-veredictos 2>/dev/null
# Solo si hay commits nuevos respecto al ultimo push (evita ruido cada 5 min)
if ! git rev-parse --quiet --verify asus/mac-veredictos >/dev/null 2>&1 \
   || [ -n "$(git log --oneline asus/mac-veredictos..HEAD 2>/dev/null)" ]; then
    git branch -f mac-veredictos HEAD 2>/dev/null || git branch mac-veredictos HEAD
    git push asus mac-veredictos --force-with-lease 2>&1 | tail -1
    echo "PUSH_VEREDICTOS_OK (rama mac-veredictos)"
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