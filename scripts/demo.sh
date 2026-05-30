#!/bin/bash
set -euo pipefail
echo "🦞 URA — Demo en vivo"
python3 --version || exit 1
curl -s http://127.0.0.1:5100/agents &>/dev/null && echo "✅ Registry OK" || {
    python3 agents/registry_api.py & sleep 2
    curl -s http://127.0.0.1:5100/agents &>/dev/null && echo "✅ Registry OK" || echo "⚠️  Registry no disponible"
}
bash ~/bin/auto_cleanup.sh 2>&1 | grep -E "Rodillo|✅|🔴"
echo "🌐 http://127.0.0.1:5101"
