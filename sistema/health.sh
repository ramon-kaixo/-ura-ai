#!/bin/bash
set -euo pipefail
# health.sh — Endpoint de salud unico para todo el ecosistema URA
echo "🩺 URA Health Check — $(date)"
echo "═══════════════════════════════"

REPORT="{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"servicios\":{"
OK=true

check() {
    local name="$1" url="$2"
    if curl -s --max-time 5 "$url" >/dev/null 2>&1; then
        echo "   ✅ $name"
        REPORT+="\"$name\":\"ok\","
    else
        echo "   🔴 $name"
        REPORT+="\"$name\":\"error\","
        OK=false
    fi
}

check "registry" "http://127.0.0.1:5100/agents"
check "dashboard" "http://127.0.0.1:5101"
check "searxng" "http://178.105.81.83:8888"
check "ollama" "http://10.164.1.99:11434/api/tags"

BUZOS=$(find "${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Enjambre/informes" -name "hallazgos_*.json" -mtime -7 2>/dev/null | wc -l | tr -d ' ')
echo "   📊 Buzos activos (7d): $BUZOS"
REPORT+="\"buzos_activos\":$BUZOS,"

DISCO=$(df -h / 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo 0)
echo "   💾 Disco: ${DISCO}%"
REPORT+="\"disco_uso_pct\":$DISCO,"

FREE=$(vm_stat 2>/dev/null | awk '/free/ {print $3}' | sed 's/\.//' || echo 0)
echo "   🧠 RAM libre: $((FREE * 4096 / 1024 / 1024)) MB"
REPORT+="\"ram_libre_mb\":$((FREE * 4096 / 1024 / 1024))"

REPORT+="}}"
echo ""
echo "$REPORT" | python3 -m json.tool 2>/dev/null || echo "$REPORT"
echo ""
[ "$OK" = true ] && echo "✅ SALUDABLE" || echo "🔴 PROBLEMAS"
