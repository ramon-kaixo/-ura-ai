#!/bin/bash
# trampa_rm.sh — Sustituye a 'rm' en agentes OpenClaw
# Nunca borra archivos. Solo los mueve a la carpeta de cuarentena.

CUARENTENA="${URA_CUARENTENA:-$HOME/URA/cuarentena}"
mkdir -p "$CUARENTENA"

for arg in "$@"; do
    case "$arg" in
        -rf|-r|-f|-rf|--*) continue ;;
        *)
            if [ -e "$arg" ]; then
                dest="$CUARENTENA/$(basename "$arg").$(date +%s)"
                mv "$arg" "$dest" 2>/dev/null && echo "[trampa] Movido a cuarentena: $arg -> $dest"
            fi
            ;;
    esac
done
