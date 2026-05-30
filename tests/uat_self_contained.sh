#!/bin/bash
set -euo pipefail
cleanup() { pkill -f "registry_api.py\|ura_dashboard.py" 2>/dev/null || true; }
trap cleanup EXIT
echo "🧪 UAT 10/10 — $(date)"
python3 agents/registry_api.py &>/dev/null &
sleep 2
P=0;F=0
curl -s http://127.0.0.1:5100/agents >/dev/null 2>&1 && echo "✅ Registry: OK" && P=$((P+1)) || echo "🔴 Registry: FAIL" && F=$((F+1))
curl -s http://127.0.0.1:5101 >/dev/null 2>&1 && echo "✅ Dashboard: OK" && P=$((P+1)) || echo "🔴 Dashboard: FAIL" && F=$((F+1))
SCORE=$((P*10/2))
echo "=== $P/2 pasados — UAT $SCORE/10 ==="
exit $F
