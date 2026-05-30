#!/bin/bash
# Plan B — Diagnóstico rápido (sin dependencias)
echo "🩺 Plan B: Health Check"
echo "═══════════════════════════"

echo -n "Python: "; python3 --version 2>&1 || echo "no encontrado"
echo -n "Git: "; git --version 2>&1 || echo "no encontrado"
echo -n "Docker: "; docker --version 2>&1 || echo "no encontrado"
echo -n ".venv: "; [ -f ~/URA/ura_ia_1972/.venv/bin/activate ] && echo "✅" || echo "❌"
echo -n "Espacio disco: "; df -h / | tail -1 | awk '{print $4 " libres"}'
echo -n "RAM: "; vm_stat 2>/dev/null | head -3 | tail -1 | awk '{print $3}'
echo -n "Timers: "; ls ~/Library/LaunchAgents/com.coderefine.*.plist 2>/dev/null | wc -l | tr -d ' '
echo " launchd"
