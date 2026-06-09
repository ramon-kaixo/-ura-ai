#!/bin/bash
# guardian_tmpfs.sh — Mueve capturas del tmpfs a disco + control de RAM
# Ejecutar cada minuto via cron: * * * * * /ruta/guardian_tmpfs.sh >/dev/null 2>&1

ORIGEN="/tmp/ura-capturas"
DESTINO="/home/ramon/URA/ura_ia_1972/storage/capturas"
MAX_MB=400

mkdir -p "$DESTINO"

# 1. Solo archivos .png visibles completos con mas de 1 minuto de vida
find "$ORIGEN" -name "*.png" -mmin +1 -print0 2>/dev/null | \
  while IFS= read -r -d "" f; do
    cp "$f" "$DESTINO/" && rm -f "$f"
  done

# 2. Control de RAM: si supera MAX_MB, purga las mas viejas del tmpfs
USADO=$(du -s "$ORIGEN" 2>/dev/null | awk "{print \$1}")
LIMITE=$((MAX_MB * 1024))

if [ -n "$USADO" ] && [ "$USADO" -gt "$LIMITE" ]; then
  find "$ORIGEN" -name "*.png" -printf "%T@ %p\n" 2>/dev/null \
    | sort -n | head -20 | cut -d" " -f2- | xargs rm -f 2>/dev/null
fi

# 3. Renombrar/limpiar huerfanos (>5 min, el proceso murio)
find "$ORIGEN" -name ".captura_*.png" -mmin +5 -print0 2>/dev/null | \
  while IFS= read -r -d "" f; do
    d=$(dirname "$f")
    b=$(basename "$f")
    b="${b#.}"
    visible="$d/$b"
    if [ ! -f "$visible" ]; then
      mv "$f" "$visible"
    else
      rm -f "$f"
    fi
  done
