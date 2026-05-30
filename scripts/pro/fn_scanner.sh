#!/bin/bash
set -euo pipefail
# FN Scanner — Detecta servicios que deberían estar corriendo pero no
echo "🔍 FN Scanner — Buscando servicios perdidos..."
FN_LOG="${HOME}/URA/ura_ia_1972/docs/pro/reports/fn_log.txt"
{
echo "=== FN Scanner: $(date) ==="
echo ""

# 1. Servicios registrados en Registry pero sin proceso activo
echo "Servicios registrados sin proceso activo:"
if curl -s http://127.0.0.1:5100/agents >/dev/null 2>&1; then
    python3 -c "
import json, os, subprocess
agents = json.loads(open('/dev/stdin').read()) if False else []
try:
    import urllib.request
    agents = json.loads(urllib.request.urlopen('http://127.0.0.1:5100/agents', timeout=3).read())
except:
    pass
for a in agents:
    port = a.get('port', 0)
    if port and port > 0:
        r = subprocess.run(['lsof', '-iTCP', f':{port}', '-sTCP:LISTEN'], capture_output=True, text=True, timeout=3)
        if r.returncode != 0:
            print(f'   👻 {a[\"id\"]} (puerto {port}): registrado pero NO escucha')
"
fi 2>/dev/null || echo "   (Registry no disponible)"

# 2. Procesos que deberían estar registrados pero no
echo ""
echo "Procesos activos NO registrados en Registry:"
ps aux 2>/dev/null | grep -E "python3.*agents/|python3.*web/" | grep -v grep | while read line; do
    cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
    pid=$(echo "$line" | awk '{print $2}')
    echo "   ❓ PID $pid: $cmd"
done

# 3. Timers launchd caídos
echo ""
echo "Timers launchd con fallos:"
launchctl list 2>/dev/null | grep -E "coderefine|ura\." | while read pid status label; do
    [ "$status" != "0" ] && [ "$status" != "-" ] 2>/dev/null && echo "   🔴 $label (exit code: $status)"
done

} > "$FN_LOG"
cat "$FN_LOG"
echo "✅ FN Scanner completado — log en $FN_LOG"
