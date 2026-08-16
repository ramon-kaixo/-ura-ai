#!/usr/bin/env bash
# check_merge_conflicts.sh — rechaza marcadores de conflicto git en el árbol
# Un marcador de conflicto commiteado rompe la build (p.ej. systemd no parsea el unit).
# Uso:
#   bash scripts/pro/check_merge_conflicts.sh [archivo...]
#   (sin argumentos escanea todos los archivos trackeados de git)
set -euo pipefail

if [ "$#" -eq 0 ]; then
    # En pre-commit se pasan los archivos staged; si no, escanear todo el árbol trackeado.
    files=$(git ls-files)
else
    files="$*"
fi

found=0
for f in $files; do
    if [ -f "$f" ] && grep -nE '^(<<<<<<< |=======$|>>>>>>> )' "$f" 2>/dev/null; then
        found=1
    fi
done

if [ "$found" -eq 1 ]; then
    echo "ERROR: se encontraron marcadores de conflicto git (<<<<<<< / ======= / >>>>>>>)." >&2
    echo "       Resuélvelos antes de commitear (git mergetool o edición manual)." >&2
    exit 1
fi

echo "OK: sin marcadores de conflicto"
exit 0
