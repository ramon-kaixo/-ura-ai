#!/bin/bash
set -euo pipefail
# diagnostico_supervivencia.sh — Identifica en que escenario de fallo estamos
echo "🩺 Diagnostico de Supervivencia — $(date)"
echo "═══════════════════════════════════════════"

echo "🖥️  Mac:"
pgrep -f "registry_api.py" >/dev/null 2>&1 && echo "   ✅ Registry activo" || echo "   🔴 Registry caido"

echo "🧠 GX10:"
if ping -c 1 -W 2 10.164.1.99 >/dev/null 2>&1; then
    echo "   ✅ Red alcanzable"
    curl -s --max-time 5 "http://10.164.1.99:11434/api/tags" >/dev/null 2>&1 && echo "   ✅ Ollama responde" || echo "   🔴 Ollama caido"
else
    echo "   🔴 Red inalcanzable"
fi

echo "🌐 Tailscale:"
tailscale status --json 2>/dev/null | jq -r '"   ✅ Conectado: \(.Self.HostName)"' 2>/dev/null || echo "   🔴 No conectado"

echo ""
echo "📋 Escenario:"
if ! pgrep -f "registry_api.py" >/dev/null 2>&1; then
    echo "   🔴 A: Mac caido"
elif ! curl -s --max-time 5 "http://10.164.1.99:11434/api/tags" >/dev/null 2>&1; then
    echo "   🔴 B: GX10 caido"
elif ! ping -c 1 -W 2 10.164.1.99 >/dev/null 2>&1; then
    echo "   🟡 C: Red caida"
else
    echo "   ✅ Sin incidencias"
fi
