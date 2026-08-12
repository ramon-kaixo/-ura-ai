#!/bin/bash
# deploy-mac.sh — Despliegue completo de la metodología/scripts a la Mac en 1 comando.
# Elimina los ~10 pasos manuales (scp sueltos, recargas launchd, reinicio TERM)
# que causaron fallos de pegado y desincronización el 2026-08-12 (TASK-20260812-010).
#
# Uso: bash scripts/pro/deploy-mac.sh [--solo-agents] [--solo-scripts]
#   (sin args)      : todo (AGENTS.md + scripts + launchd + reinicio TERM + verificación)
#   --solo-agents   : solo copiar AGENTS.md.global a ~/.config/opencode/AGENTS.md
#   --solo-scripts  : solo copiar scripts y recargar launchd (sin reiniciar TERM)
#
# Requiere: acceso ssh a ramonesnaola@10.164.1.26 (clave configurada).

set -u
MAC="ramonesnaola@10.164.1.26"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
GLOBAL="$REPO/deploy/engineering/AGENTS.md.global"
SCRIPTS_MAC=(
  "$REPO/deploy/mac/despertador-fondo.sh:~/bin/despertador-fondo.sh"
  "$REPO/deploy/mac/ura-fondo-health.sh:~/bin/ura-fondo-health.sh"
)
LAUNCHD_FONDO="com.ura.fondo-wake"

echo "=== deploy-mac.sh — despliegue a la Mac ==="

if [ "${1:-}" != "--solo-scripts" ]; then
    echo "[1/4] Copiando AGENTS.md.global → ~/.config/opencode/AGENTS.md"
    scp -q "$GLOBAL" "$MAC:~/.config/opencode/AGENTS.md" || { echo "  ❌ scp AGENTS falló"; exit 1; }
fi

echo "[2/4] Copiando scripts → ~/bin/"
for pair in "${SCRIPTS_MAC[@]}"; do
    src="${pair%%:*}"; dst="${pair##*:}"
    scp -q "$src" "$MAC:$dst" || { echo "  ❌ scp $src falló"; exit 1; }
done
ssh "$MAC" "chmod +x ~/bin/despertador-fondo.sh ~/bin/ura-fondo-health.sh" 2>/dev/null

echo "[3/4] Recargando launchd (fondo-wake)"
ssh "$MAC" "launchctl unload ~/Library/LaunchAgents/$LAUNCHD_FONDO.plist 2>/dev/null; launchctl load ~/Library/LaunchAgents/$LAUNCHD_FONDO.plist; sleep 2; launchctl list | grep $LAUNCHD_FONDO"

if [ "${1:-}" = "--solo-scripts" ]; then
    echo "[4/4] (omitido: reinicio TERM)"
else
    echo "[4/4] Reiniciando servidor TERM (carga config/agente nuevos)"
    ssh "$MAC" "PID=\$(pgrep -f 'opencode web --port 8091' | head -1); [ -n \"\$PID\" ] && kill \$PID; sleep 8; curl -s -o /dev/null -w 'TERM HTTP %{http_code}\n' --max-time 5 http://127.0.0.1:8091/ || echo '  ❌ TERM no responde'"
fi

echo "=== Verificación ==="
ssh "$MAC" "echo 'AGENTS:'; head -1 ~/.config/opencode/AGENTS.md; echo 'Scripts:'; ls -la ~/bin/despertador-fondo.sh ~/bin/ura-fondo-health.sh 2>&1 | awk '{print \$5, \$9}'; echo 'Agente revisor-fondo:'; ~/.opencode/bin/opencode agent list 2>&1 | grep -c revisor-fondo"
echo "=== deploy-mac.sh completo ==="
