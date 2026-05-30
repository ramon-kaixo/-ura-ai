#!/bin/bash
set -euo pipefail
echo "⚠️  PLAN B — RESET DE FÁBRICA"
echo "Esto eliminará el .venv, quarantine, y reiniciará servicios."
echo "Presiona Ctrl+C para cancelar o Enter para continuar..."
read -r

# Backup de emergencia antes de reset
bash "$(dirname "$0")/emergency_backup.sh"

# Detener servicios
for plist in ~/Library/LaunchAgents/com.coderefine.*.plist; do
    launchctl unload "$plist" 2>/dev/null || true
done

# Limpiar
rm -rf .venv quarantine logs/autocleanup_*.log

# Recrear .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
[ -f requirements.txt ] && pip install -r requirements.txt -q

# Recargar servicios
for plist in ~/Library/LaunchAgents/com.coderefine.*.plist; do
    launchctl load "$plist" 2>/dev/null || true
done

echo "✅ Reset completado. Ejecuta ~/bin/auto_cleanup.sh para el primer ciclo."
