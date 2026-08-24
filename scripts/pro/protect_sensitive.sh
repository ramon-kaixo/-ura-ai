#!/bin/bash
# protect_sensitive.sh — asegura chattr +i sobre ficheros sensibles (2026-08-25)
# NOTA: requiere sudo interactivo; si se lanza sin TTY sudo, los chattr fallan silenciosos.
set -u
REPO="$HOME/URA/ura_ia_1972"
for f in config/system_config.json deploy/lildax_config.json deploy/sync_to_asus.sh core/debate/committee_config.json; do
  [ -f "$REPO/$f" ] || { echo "FALTA $f"; continue; }
  if lsattr "$REPO/$f" 2>/dev/null | cut -d' ' -f1 | grep -q -- '-i-'; then
    echo "OK      $f"
  else
    echo "PROTEGIENDO $f"; sudo chattr +i "$REPO/$f" || echo "ERROR sudo en $f"
  fi
done
