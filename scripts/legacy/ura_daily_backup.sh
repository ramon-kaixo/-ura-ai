#!/bin/bash
# Backup diario URA — Configs críticas
# Programado: 03:00 cada día
set -e

DEST=~/ura_backups/daily/$(date +%Y%m%d)
mkdir -p "$DEST"
LOG=~/ura_backups/daily.log

echo "=== Backup $(date) ===" >> "$LOG"

# Configs críticas
cp ~/URA/ura_ia_1972/.env "$DEST/env" 2>>"$LOG" && echo "✅ .env" >> "$LOG"
cp ~/URA/ura_ia_1972/ecosystem.config.js "$DEST/ecosystem.config.js" 2>>"$LOG" && echo "✅ ecosystem" >> "$LOG"
cp ~/URA/ura_ia_1972/config/network_topology.md "$DEST/network_topology.md" 2>>"$LOG"
cp -r ~/.ssh "$DEST/ssh" 2>>"$LOG" && echo "✅ ssh" >> "$LOG"
cp ~/.pm2/dump.pm2 "$DEST/pm2.dump" 2>>"$LOG" && echo "✅ pm2 dump" >> "$LOG"
cp ~/Library/LaunchAgents/com.ura.*.plist "$DEST/" 2>>"$LOG"

# Snapshot estado
tailscale status > "$DEST/tailscale.txt" 2>>"$LOG"
pm2 list > "$DEST/pm2.txt" 2>>"$LOG"

# Limpieza: conservar solo 14 días
find ~/ura_backups/daily -maxdepth 1 -type d -mtime +14 -exec rm -rf {} + 2>/dev/null

echo "✅ Backup en $DEST" >> "$LOG"
