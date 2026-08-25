#!/usr/bin/env bash
# exportar_unidades_systemd.sh — Versiona la flota ura-* de /etc al repo
# Cierra el punto ciego detectado en TASK-20260825-002: 66 unidades en
# produccion sin copia versionada (a 2026-08-25).
#
# Uso (GX10): bash scripts/pro/exportar_unidades_systemd.sh
# Salida: deploy/systemd-prod/<unidades> + MANIFEST.sha256
set -euo pipefail

REPO="${REPO:-$HOME/URA/ura_ia_1972}"
DEST="$REPO/deploy/systemd-prod"
mkdir -p "$DEST"

N=0
for src in /etc/systemd/system/ura-*.service /etc/systemd/system/ura-*.timer; do
  [ -f "$src" ] || continue
  [ -L "$src" ] && continue
  base=$(basename "$src")
  cmp -s "$src" "$DEST/$base" 2>/dev/null || cp "$src" "$DEST/$base"
  N=$((N + 1))
done

{
  echo "# Manifest flota systemd-prod — $(date "+%Y-%m-%d %H:%M") — ${N} unidades"
  cd "$DEST"
  ls ura-*.service ura-*.timer 2>/dev/null | sort | while read -r f; do
    sha256sum "$f"
  done
} > "$DEST/MANIFEST.sha256"

echo "Exportadas ${N} unidades -> deploy/systemd-prod/ (manifest regenerado)"
